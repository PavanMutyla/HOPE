import uuid
from dataclasses import dataclass

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.kokoro.tts import KOKORO_CACHE_DIR, KokoroTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from openai import AsyncOpenAI

from core.voice.agent import VoiceAgent
from core.voice.context_meter import ContextMeter, resolve_context_limit
from core.voice.summarizer import ContextSummarizer
from core.observability import LangfuseObserver, LangfuseTracer
from core.status import StatusMonitor, StatusPanel
from memory.episodic_memory.store import EpisodicMemory
from settings import settings


def _build_kokoro_tts(voice_id: str) -> KokoroTTSService:
    """Construct KokoroTTSService, recovering once from a corrupted/partial model cache.

    Pipecat auto-downloads the model on first use but only checks that the
    cache files *exist* — a truncated download (e.g. an interrupted transfer
    on first run on a new machine) leaves a file that exists but fails to
    load. Detect that case, delete the cache, and let pipecat re-download.
    Any other failure is not ours to interpret — let it propagate.
    """
    model_file = KOKORO_CACHE_DIR / "kokoro-v1.0.onnx"
    voices_file = KOKORO_CACHE_DIR / "voices-v1.0.bin"

    if not model_file.exists() or not voices_file.exists():
        logger.info("Kokoro TTS model not found locally — downloading (~300MB, one-time)...")

    try:
        return KokoroTTSService(settings=KokoroTTSService.Settings(voice=voice_id))
    except Exception:
        if not model_file.exists() and not voices_file.exists():
            raise
        logger.warning(
            "Kokoro TTS model cache looks corrupted or incomplete — deleting and re-downloading..."
        )
        model_file.unlink(missing_ok=True)
        voices_file.unlink(missing_ok=True)
        return KokoroTTSService(settings=KokoroTTSService.Settings(voice=voice_id))


@dataclass
class VoicePipelineBundle:
    pipeline: Pipeline
    worker: PipelineWorker
    llm: OpenAILLMService
    tts: KokoroTTSService
    context: LLMContext
    transport: LocalAudioTransport
    panel: StatusPanel
    tracer: LangfuseTracer
    meter: ContextMeter
    episodic_memory: EpisodicMemory


def build_pipeline(agent: VoiceAgent, tools: list[FunctionSchema]) -> VoicePipelineBundle:
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_enabled=True,
            audio_out_sample_rate=16000,
        )
    )

    stt = OpenAISTTService(
        api_key=settings.openai_api_key,
        settings=OpenAISTTService.Settings(
            model=settings.stt_model,
            language="en",
            prompt="Pavan is speaking. Conversation about business, tech, and personal topics.",
        ),
    )

    llm = OpenAILLMService(
        api_key=settings.openai_api_key,
        settings=OpenAILLMService.Settings(model=settings.llm_model),
    )

    tts = _build_kokoro_tts(agent.voice_id)

    context = LLMContext(
        messages=[{"role": "system", "content": agent.system_prompt}],
        tools=ToolsSchema(standard_tools=tools),
    )

    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    confidence=0.7,
                    start_secs=0.2,
                    stop_secs=0.8,
                    min_volume=0.6,
                )
            ),
            user_turn_strategies=UserTurnStrategies(
                stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
            ),
        ),
    )

    panel = StatusPanel()
    panel.set_agent(agent.name)
    pre_monitor = StatusMonitor(panel)
    post_monitor = StatusMonitor(panel)

    tracer = LangfuseTracer()
    pre_trace = LangfuseObserver(tracer)
    post_trace = LangfuseObserver(tracer)

    meter = ContextMeter(
        context_limit=resolve_context_limit(
            f"{settings.llm_provider}/{settings.llm_model}", settings.llm_context_limit
        ),
        threshold=settings.context_summarize_threshold,
    )
    episodic_memory = EpisodicMemory()
    summarizer = ContextSummarizer(
        context=context,
        meter=meter,
        panel=panel,
        client=AsyncOpenAI(api_key=settings.openai_api_key),
        episodic_memory=episodic_memory,
        session_id=str(uuid.uuid4()),
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        pre_monitor,
        pre_trace,
        context_aggregator.user(),
        llm,
        post_monitor,
        post_trace,
        summarizer,
        tts,
        context_aggregator.assistant(),
        transport.output(),
    ])

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    return VoicePipelineBundle(
        pipeline=pipeline,
        worker=worker,
        llm=llm,
        tts=tts,
        context=context,
        transport=transport,
        panel=panel,
        tracer=tracer,
        meter=meter,
        episodic_memory=episodic_memory,
    )

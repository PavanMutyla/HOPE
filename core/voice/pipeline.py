import uuid
from dataclasses import dataclass

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
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from openai import AsyncOpenAI

from core.voice.agent import VoiceAgent
from core.voice.context_meter import ContextMeter, resolve_context_limit
from core.voice.kokoro_cache import ensure_kokoro_files, recover_corrupted_kokoro_cache
from core.voice.summarizer import ContextSummarizer
from core.voice.team_broadcast import TeamBroadcastObserver
from core.voice.team_registry import team_registry
from core.observability import LangfuseObserver, LangfuseTracer
from core.status import StatusMonitor, StatusPanel
from memory.episodic_memory.store import EpisodicMemory
from memory.procedural_memory.store import ProceduralMemory
from memory.semantic_memory.store import SemanticMemory
from settings import settings


def _build_kokoro_tts(voice_id: str) -> KokoroTTSService:
    """Construct KokoroTTSService, recovering once from a corrupted/partial model cache.

    Any other failure is not ours to interpret — let it propagate.
    """
    model_file, voices_file = ensure_kokoro_files()

    try:
        return KokoroTTSService(settings=KokoroTTSService.Settings(voice=voice_id))
    except Exception:
        if not model_file.exists() and not voices_file.exists():
            raise
        recover_corrupted_kokoro_cache(model_file, voices_file)
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
    semantic_memory: SemanticMemory
    procedural_memory: ProceduralMemory
    summarizer: ContextSummarizer


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

    team_broadcast = TeamBroadcastObserver(
        team_registry, AsyncOpenAI(api_key=settings.openai_api_key)
    )

    meter = ContextMeter(
        context_limit=resolve_context_limit(
            f"{settings.llm_provider}/{settings.llm_model}", settings.llm_context_limit
        ),
        threshold=settings.context_summarize_threshold,
    )
    episodic_memory = EpisodicMemory()
    semantic_memory = SemanticMemory()
    procedural_memory = ProceduralMemory()
    summarizer = ContextSummarizer(
        context=context,
        meter=meter,
        panel=panel,
        client=AsyncOpenAI(api_key=settings.openai_api_key),
        episodic_memory=episodic_memory,
        session_id=str(uuid.uuid4()),
        semantic_memory=semantic_memory,
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        team_broadcast,
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
        semantic_memory=semantic_memory,
        procedural_memory=procedural_memory,
        summarizer=summarizer,
    )

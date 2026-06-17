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
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from core.voice.agent import VoiceAgent
from core.observability import LangfuseObserver, LangfuseTracer
from core.status import StatusMonitor, StatusPanel
from settings import settings


@dataclass
class VoicePipelineBundle:
    pipeline: Pipeline
    worker: PipelineWorker
    llm: OpenAILLMService
    tts: CartesiaTTSService
    context: LLMContext
    transport: LocalAudioTransport
    panel: StatusPanel
    tracer: LangfuseTracer


def build_pipeline(agent: VoiceAgent, tools: list[FunctionSchema]) -> VoicePipelineBundle:
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_enabled=True,
            audio_out_sample_rate=16000,
            input_device_index=16,
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

    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        settings=CartesiaTTSService.Settings(voice=agent.voice_id),
    )

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
    pre_monitor = StatusMonitor(panel)
    post_monitor = StatusMonitor(panel)

    tracer = LangfuseTracer()
    pre_trace = LangfuseObserver(tracer)
    post_trace = LangfuseObserver(tracer)

    pipeline = Pipeline([
        transport.input(),
        stt,
        pre_monitor,
        pre_trace,
        context_aggregator.user(),
        llm,
        post_monitor,
        post_trace,
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
    )

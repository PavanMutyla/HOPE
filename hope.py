import asyncio

from loguru import logger

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext, ToolsSchema
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.workers.runner import WorkerRunner

from core.observability import LangfuseTracer, LangfuseObserver
from core.prompt import SYSTEM_PROMPT
from core.status import StatusPanel, StatusMonitor
from settings import settings
from tools.registry import delegate_to_atlas_schema, delegate_to_atlas_handler


async def main():
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
        settings=CartesiaTTSService.Settings(voice=settings.cartesia_voice_id),
    )

    tools = ToolsSchema(function_schemas=[delegate_to_atlas_schema])
    context = LLMContext(
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        tools=tools,
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
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    llm.register_function(
        "delegate_to_atlas",
        delegate_to_atlas_handler,
        cancel_on_interruption=False,
    )

    @worker.event_handler("on_pipeline_started")
    async def on_pipeline_started(worker, frame):
        logger.info("Pipeline started — queuing greeting")
        context.add_message({"role": "developer", "content": "Say a short hello to Pavan."})
        await worker.queue_frames([LLMRunFrame()])

    logger.info("HOPE is ready — start speaking!")
    panel.start()
    try:
        runner = WorkerRunner(handle_sigint=True)
        await runner.add_workers(worker)
        await runner.run()
    finally:
        panel.stop()
        tracer.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

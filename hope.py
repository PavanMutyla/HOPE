import asyncio
import time

from loguru import logger
from openai import AsyncOpenAI

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

from core.prompt import SYSTEM_PROMPT
from core.settings import settings
from core.status import StatusPanel, StatusMonitor


async def warmup_services():
    """Pre-establish TLS connection to api.openai.com — shared by STT, LLM, and TTS."""
    start = time.perf_counter()
    logger.info("Warming up services...")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    # A minimal LLM call is enough — all OpenAI services reuse the same connection pool.
    await client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1,
    )

    elapsed = time.perf_counter() - start
    logger.info(f"Services ready in {elapsed:.2f}s")


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

    vad = VADProcessor(vad_analyzer=SileroVADAnalyzer())

    stt = OpenAISTTService(
        api_key=settings.openai_api_key,
        model=settings.stt_model,
        language="en",
        prompt="Pavan is speaking. Conversation about business, tech, and personal topics.",
    )

    llm = OpenAILLMService(
        api_key=settings.openai_api_key,
        settings=OpenAILLMService.Settings(model=settings.llm_model),
    )

    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        settings=CartesiaTTSService.Settings(voice=settings.cartesia_voice_id),
    )

    context = LLMContext(messages=[{"role": "system", "content": SYSTEM_PROMPT}])
    context_aggregator = LLMContextAggregatorPair(context)

    panel = StatusPanel()
    pre_monitor = StatusMonitor(panel)
    post_monitor = StatusMonitor(panel)

    pipeline = Pipeline([
        transport.input(),
        vad,
        stt,
        pre_monitor,
        context_aggregator.user(),
        llm,
        post_monitor,
        tts,
        context_aggregator.assistant(),
        transport.output(),
    ])

    worker = PipelineWorker(pipeline, params=PipelineParams())

    await warmup_services()
    logger.info("HOPE is ready — start speaking!")
    panel.start()
    try:
        runner = PipelineRunner()
        await runner.run(worker)
    finally:
        panel.stop()


if __name__ == "__main__":
    asyncio.run(main())

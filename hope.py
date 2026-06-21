import asyncio

from loguru import logger
from pipecat.frames.frames import LLMRunFrame
from pipecat.workers.runner import WorkerRunner

from sub_agents.atlas.agent import atlas_agent
from core.voice.agent import AgentRegistry, VoiceAgent
from core.voice.orchestrator import VoiceOrchestrator
from core.voice.pipeline import build_pipeline
from core.prompt import SYSTEM_PROMPT
from settings import settings
from tools.registry import ALL_SCHEMAS, setup as setup_tools


hope_agent = VoiceAgent(
    name="hope",
    system_prompt=SYSTEM_PROMPT,
    voice_id=settings.kokoro_voice_id,
)


async def main():
    registry = AgentRegistry()
    registry.register(hope_agent)
    registry.register(atlas_agent)

    bundle = build_pipeline(hope_agent, ALL_SCHEMAS)
    orchestrator = VoiceOrchestrator(registry, bundle)

    setup_tools(orchestrator)

    @bundle.worker.event_handler("on_pipeline_started")
    async def on_pipeline_started(worker, frame):
        logger.info("Pipeline started — queuing greeting")
        bundle.context.add_message({"role": "developer", "content": "Say a short hello to Pavan."})
        await bundle.worker.queue_frames([LLMRunFrame()])

    logger.info("HOPE is ready — start speaking!")
    bundle.panel.start()
    try:
        runner = WorkerRunner(handle_sigint=True)
        await runner.add_workers(bundle.worker)
        await runner.run()
    finally:
        bundle.panel.stop()
        bundle.tracer.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

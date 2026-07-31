import asyncio

from loguru import logger
from openai import AsyncOpenAI
from pipecat.frames.frames import LLMRunFrame
from pipecat.workers.runner import WorkerRunner

from sub_agents.atlas.agent import atlas_agent
from sub_agents.atlas.team import build_atlas_team_member
from core.voice.agent import AgentRegistry, VoiceAgent
from core.voice.orchestrator import VoiceOrchestrator
from core.voice.pipeline import build_pipeline
from core.voice.summarizer import inject_warm_start, upgrade_pending_episodes
from core.voice.team_registry import team_registry
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

    atlas_team_member = build_atlas_team_member()
    team_registry.register(atlas_team_member)

    bundle = build_pipeline(hope_agent, ALL_SCHEMAS)
    orchestrator = VoiceOrchestrator(registry, bundle)

    setup_tools(orchestrator)

    await inject_warm_start(bundle.episodic_memory, bundle.context)

    asyncio.create_task(
        upgrade_pending_episodes(
            bundle.episodic_memory,
            AsyncOpenAI(api_key=settings.openai_api_key),
            bundle.semantic_memory,
        )
    )

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
        await bundle.summarizer.flush()
        bundle.episodic_memory.close()
        bundle.blackboard.close()
        atlas_team_member.voice.close()


if __name__ == "__main__":
    asyncio.run(main())

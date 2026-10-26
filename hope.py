import asyncio
import os
import signal
import subprocess
from pathlib import Path

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

_REPO_ROOT = Path(__file__).parent
_DASHBOARD_DIR = _REPO_ROOT / "dashboard"
_REFLEX_BIN = _REPO_ROOT / ".venv" / "bin" / "reflex"
_DASHBOARD_PORT = 3000


hope_agent = VoiceAgent(
    name="hope",
    system_prompt=SYSTEM_PROMPT,
    voice_id=settings.kokoro_voice_id,
)


def _start_dashboard() -> subprocess.Popen | None:
    """Launches the dashboard as its own process group (Reflex's own frontend
    build spawns bun/node/granian children that a plain terminate() won't
    reach — start_new_session=True lets _stop_dashboard() kill the whole
    group at once). Its stdout/stderr are left to inherit this terminal —
    this terminal is meant to show Reflex's own compile/dev-server output;
    HOPE's own logs are deliberately routed elsewhere (see main()) so the two
    don't get intermixed."""
    if not settings.dashboard_autostart:
        return None
    if not _REFLEX_BIN.exists():
        logger.warning(f"Dashboard autostart skipped — {_REFLEX_BIN} not found.")
        return None

    proc = subprocess.Popen(
        [str(_REFLEX_BIN), "run"],
        cwd=_DASHBOARD_DIR,
        start_new_session=True,
    )
    logger.debug(f"Dashboard subprocess started (pid {proc.pid}).")
    print(f"Dashboard: http://localhost:{_DASHBOARD_PORT} (watch below for the actual port if that one's taken)")
    return proc


def _stop_dashboard(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


_LIVE_HEARTBEAT_SECONDS = 10


async def _live_heartbeat(live_feed) -> None:
    """Tell the dashboard this process is still alive.

    Without it, the dashboard can only see the last state change, and a HOPE
    sitting silently in `listening` is indistinguishable from a HOPE that was
    killed while listening. Best-effort: a failure here is a stale dashboard,
    never a stalled pipeline.
    """
    while True:
        await asyncio.sleep(_LIVE_HEARTBEAT_SECONDS)
        try:
            await asyncio.to_thread(live_feed.heartbeat)
        except Exception:
            logger.exception("Live heartbeat failed — dashboard may show HOPE as down")


async def main():
    # This terminal is reserved for the dashboard subprocess's own output
    # (see _start_dashboard) — HOPE's own logs go only to hope_log_path,
    # which the dashboard's terminal card tails. logger.remove() drops
    # loguru's default stderr sink; level="DEBUG" (not settings.log_level)
    # keeps this file a full match for what used to print to this terminal,
    # including core/status.py's per-turn debug lines.
    logger.remove()
    Path(settings.hope_log_path).parent.mkdir(parents=True, exist_ok=True)
    logger.add(settings.hope_log_path, level="DEBUG", rotation="5 MB", retention=3, enqueue=True)

    dashboard_proc = _start_dashboard()
    try:
        registry = AgentRegistry()
        registry.register(hope_agent)
        registry.register(atlas_agent)

        atlas_team_member = build_atlas_team_member()
        team_registry.register(atlas_team_member)

        bundle = build_pipeline(hope_agent, ALL_SCHEMAS)
        orchestrator = VoiceOrchestrator(registry, bundle)

        setup_tools(orchestrator)

        await inject_warm_start(bundle.episodic_memory, bundle.context)

        asyncio.create_task(_live_heartbeat(bundle.live_feed))

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
            bundle.board.close()
            # Flag the pipeline down before closing, so the dashboard renders
            # "not running" instead of a frozen live panel. Turns are left in
            # place — the next run clears them.
            bundle.live_feed.end_session()
            bundle.live_feed.close()
            atlas_team_member.voice.close()
    finally:
        _stop_dashboard(dashboard_proc)


if __name__ == "__main__":
    asyncio.run(main())

"""Unit tests for context summarization pure functions."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pipecat.frames.frames import MetricsFrame, TextFrame
from pipecat.metrics.metrics import LLMTokenUsage, LLMUsageMetricsData, TTFBMetricsData
from pipecat.processors.frame_processor import FrameDirection

from core.voice.agent_state import agent_state
from core.voice.context_meter import ContextMeter
from core.voice.summarizer import (
    UNSUMMARIZED_MARKER,
    ContextSummarizer,
    build_summary_request,
    inject_warm_start,
    rebuild_context,
    split_for_summary,
    upgrade_pending_episodes,
)


def msgs(*roles: str) -> list[dict]:
    return [{"role": r, "content": f"{r}-{i}"} for i, r in enumerate(roles)]


@pytest.mark.unit
def test_split_keeps_system_and_recent():
    messages = msgs("system", "user", "assistant", "user", "assistant", "user", "assistant")
    system_msgs, head, recent = split_for_summary(messages, keep_recent=2)
    assert system_msgs == [messages[0]]
    assert head == messages[1:5]
    assert recent == messages[5:]


@pytest.mark.unit
def test_split_nothing_to_summarize_when_short():
    messages = msgs("system", "user", "assistant")
    system_msgs, head, recent = split_for_summary(messages, keep_recent=6)
    assert head == []
    assert recent == messages[1:]


@pytest.mark.unit
def test_split_never_orphans_tool_results():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
        {"role": "tool", "content": "result", "tool_call_id": "t1"},
        {"role": "assistant", "content": "a1"},
    ]
    # keep_recent=2 would put the boundary ON the tool message — it must
    # slide back to include the assistant tool_calls message that owns it
    system_msgs, head, recent = split_for_summary(messages, keep_recent=2)
    assert recent[0]["role"] == "assistant"
    assert recent[0].get("tool_calls")
    assert head == [messages[1]]


@pytest.mark.unit
def test_split_without_system_message():
    messages = msgs("user", "assistant", "user", "assistant")
    system_msgs, head, recent = split_for_summary(messages, keep_recent=2)
    assert system_msgs == []
    assert head == messages[:2]
    assert recent == messages[2:]


@pytest.mark.unit
def test_split_keep_recent_zero_summarizes_everything():
    messages = msgs("system", "user", "assistant", "user")
    system_msgs, head, recent = split_for_summary(messages, keep_recent=0)
    assert system_msgs == [messages[0]]
    assert head == messages[1:]
    assert recent == []


@pytest.mark.unit
def test_split_negative_keep_recent_behaves_like_zero():
    messages = msgs("user", "assistant")
    system_msgs, head, recent = split_for_summary(messages, keep_recent=-3)
    assert system_msgs == []
    assert head == messages
    assert recent == []


@pytest.mark.unit
def test_build_summary_request_contains_transcript():
    head = msgs("user", "assistant")
    request = build_summary_request(head)
    assert request[0]["role"] == "system"
    transcript = request[1]["content"]
    assert "user-0" in transcript
    assert "assistant-1" in transcript


@pytest.mark.unit
def test_rebuild_context_order():
    system_msgs = [{"role": "system", "content": "sys"}]
    recent = msgs("user", "assistant")
    rebuilt = rebuild_context(system_msgs, "the summary", recent)
    assert rebuilt[0]["role"] == "system"
    assert rebuilt[1]["role"] == "developer"
    assert "the summary" in rebuilt[1]["content"]
    assert rebuilt[2:] == recent


def make_usage_frame(prompt: int, completion: int) -> MetricsFrame:
    return MetricsFrame(data=[
        LLMUsageMetricsData(
            processor="llm",
            value=LLMTokenUsage(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=prompt + completion,
            ),
        )
    ])


def make_openai_client(summary_text: str = "summary") -> AsyncMock:
    client = AsyncMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = summary_text
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


def make_context(messages: list[dict]) -> MagicMock:
    context = MagicMock()
    context.messages = messages
    def set_messages(new):
        messages[:] = new
    context.set_messages = set_messages
    return context


def make_episodic_memory() -> MagicMock:
    return MagicMock()


TEST_SESSION_ID = "test-session"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_metrics_update_meter_and_panel():
    meter = ContextMeter(context_limit=1000)
    panel = MagicMock()
    summarizer = ContextSummarizer(
        context=make_context([]), meter=meter, panel=panel, client=make_openai_client(),
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer._handle_metrics(make_usage_frame(100, 20))
    assert meter.last_prompt_tokens == 100
    panel.set_usage.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_below_threshold_does_not_summarize():
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client()
    summarizer = ContextSummarizer(
        context=make_context([]), meter=meter, panel=MagicMock(), client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer._handle_metrics(make_usage_frame(100, 20))
    assert summarizer._summary_task is None
    client.chat.completions.create.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_at_threshold_summarizes_and_rewrites_context():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client("compressed history")
    context = make_context(messages)
    summarizer = ContextSummarizer(
        context=context, meter=meter, panel=MagicMock(), client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    summarizer._handle_metrics(make_usage_frame(900, 50))
    assert summarizer._summary_task is not None
    await summarizer._summary_task

    client.chat.completions.create.assert_awaited_once()
    # summary output is capped at 20% of the context window (1000 → 200)
    assert client.chat.completions.create.await_args.kwargs["max_tokens"] == 200
    assert messages[0] == {"role": "system", "content": "sys"}
    assert messages[1]["role"] == "developer"
    assert "compressed history" in messages[1]["content"]
    assert [m["content"] for m in messages[2:]] == ["m6", "m7", "m8", "m9"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_summarize_writes_episodic_memory():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    expected_head = messages[1:7]  # captured before summarization mutates `messages` in place
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client("compressed history")
    context = make_context(messages)
    episodic_memory = make_episodic_memory()
    summarizer = ContextSummarizer(
        context=context, meter=meter, panel=MagicMock(), client=client,
        episodic_memory=episodic_memory, session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    summarizer._handle_metrics(make_usage_frame(900, 50))
    await summarizer._summary_task

    episodic_memory.write.assert_called_once_with(
        agent=agent_state.active,
        session_id=TEST_SESSION_ID,
        reason="threshold",
        span_turns=6,  # len(expected_head) — folded head, before the keep_recent=4 tail
        summary="compressed history",
        messages=expected_head,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_summarize_does_not_write_episodic_memory():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client()
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    episodic_memory = make_episodic_memory()
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=meter, panel=MagicMock(), client=client,
        episodic_memory=episodic_memory, session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    summarizer._handle_metrics(make_usage_frame(900, 50))
    await summarizer._summary_task

    episodic_memory.write.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_episodic_write_failure_does_not_raise_or_undo_summarization():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client("compressed history")
    episodic_memory = MagicMock()
    episodic_memory.write.side_effect = RuntimeError("db is on fire")
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=meter, panel=MagicMock(), client=client,
        episodic_memory=episodic_memory, session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    summarizer._handle_metrics(make_usage_frame(900, 50))
    await summarizer._summary_task  # must not raise despite the episodic write failing

    assert messages[1]["role"] == "developer"
    assert "compressed history" in messages[1]["content"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_messages_added_during_summarization_survive():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client()
    context = make_context(messages)

    async def slow_create(**kwargs):
        # a new turn arrives while the summary call is in flight
        messages.append({"role": "user", "content": "mid-flight"})
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "summary"
        return response

    client.chat.completions.create = AsyncMock(side_effect=slow_create)
    summarizer = ContextSummarizer(
        context=context, meter=meter, panel=MagicMock(), client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    summarizer._handle_metrics(make_usage_frame(900, 50))
    await summarizer._summary_task
    assert messages[-1] == {"role": "user", "content": "mid-flight"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_agent_switch_during_summarization_is_not_reverted():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client()
    context = make_context(messages)

    async def slow_create(**kwargs):
        # AgentRegistry.switch() mutates messages[0] mid-flight, e.g. as a
        # result of an agent-to-agent handoff that happens while the
        # summarization call is in progress.
        messages[0] = {"role": "system", "content": "NEW AGENT PROMPT"}
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "summary"
        return response

    client.chat.completions.create = AsyncMock(side_effect=slow_create)
    summarizer = ContextSummarizer(
        context=context, meter=meter, panel=MagicMock(), client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    summarizer._handle_metrics(make_usage_frame(900, 50))
    await summarizer._summary_task

    assert messages[0] == {"role": "system", "content": "NEW AGENT PROMPT"}
    assert messages[1]["role"] == "developer"
    assert [m["content"] for m in messages[2:]] == ["m6", "m7", "m8", "m9"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_double_fire_while_task_running():
    messages = [{"role": "system", "content": "sys"},
                *[{"role": "user", "content": f"m{i}"} for i in range(10)]]
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client()
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_create(**kwargs):
        started.set()
        await release.wait()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "summary"
        return response

    client.chat.completions.create = AsyncMock(side_effect=blocked_create)
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=meter, panel=MagicMock(), client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    summarizer._handle_metrics(make_usage_frame(900, 50))
    await started.wait()
    first_task = summarizer._summary_task
    summarizer._handle_metrics(make_usage_frame(910, 50))
    assert summarizer._summary_task is first_task  # no second task spawned
    release.set()
    await first_task
    assert client.chat.completions.create.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_summarize_failure_recovers_and_retries():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    meter = ContextMeter(context_limit=1000)
    client = make_openai_client("compressed history")
    client.chat.completions.create = AsyncMock(
        side_effect=[RuntimeError("boom"), client.chat.completions.create.return_value]
    )
    context = make_context(messages)
    summarizer = ContextSummarizer(
        context=context, meter=meter, panel=MagicMock(), client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4

    snapshot = list(messages)
    summarizer._handle_metrics(make_usage_frame(900, 50))
    first_task = summarizer._summary_task
    assert first_task is not None
    await first_task  # must not raise — exception is caught and logged
    assert messages == snapshot  # failed summarization leaves context untouched

    summarizer._handle_metrics(make_usage_frame(900, 50))
    second_task = summarizer._summary_task
    assert second_task is not first_task  # old task was done, so a new one spawns
    await second_task

    assert client.chat.completions.create.await_count == 2
    assert messages[0] == {"role": "system", "content": "sys"}
    assert messages[1]["role"] == "developer"
    assert "compressed history" in messages[1]["content"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ttfb_metrics_recorded_without_usage_update():
    meter = ContextMeter(context_limit=1000)
    panel = MagicMock()
    summarizer = ContextSummarizer(
        context=make_context([]), meter=meter, panel=panel, client=make_openai_client(),
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    frame = MetricsFrame(data=[TTFBMetricsData(processor="llm", value=0.37)])

    summarizer._handle_metrics(frame)

    assert meter.last_ttfb == 0.37
    panel.set_usage.assert_not_called()
    assert summarizer._summary_task is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_frame_pushes_all_frames_through():
    # Driving the real pipecat process_frame path requires a StartFrame to
    # have gone through FrameProcessor.__start(), which in turn needs a
    # TaskManager wired up via setup() (full pipeline/PipelineTask harness).
    # That's disproportionate for a unit test, so instead we spy on
    # push_frame directly and drive process_frame with plain frames — this
    # exercises the exact dispatch logic in ContextSummarizer.process_frame
    # (call _handle_metrics for MetricsFrame, always push_frame) without
    # needing the surrounding pipeline machinery.
    meter = ContextMeter(context_limit=1000)
    panel = MagicMock()
    client = make_openai_client()
    summarizer = ContextSummarizer(
        context=make_context([]), meter=meter, panel=panel, client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )
    summarizer.push_frame = AsyncMock()
    summarizer._handle_metrics = MagicMock(wraps=summarizer._handle_metrics)

    metrics_frame = make_usage_frame(100, 20)  # below threshold
    await summarizer.process_frame(metrics_frame, FrameDirection.DOWNSTREAM)

    other_frame = TextFrame(text="hello")
    await summarizer.process_frame(other_frame, FrameDirection.DOWNSTREAM)

    assert summarizer.push_frame.await_count == 2
    summarizer.push_frame.assert_any_await(metrics_frame, FrameDirection.DOWNSTREAM)
    summarizer.push_frame.assert_any_await(other_frame, FrameDirection.DOWNSTREAM)
    summarizer._handle_metrics.assert_called_once_with(metrics_frame)


# ─── flush() — session-close archive (Trigger B) ──────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_flush_writes_raw_archive_tagged_session_end_raw():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "how do I deploy this?"},
        {"role": "assistant", "content": "run the deploy script"},
    ]
    episodic_memory = make_episodic_memory()
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=ContextMeter(context_limit=1000),
        panel=MagicMock(), client=make_openai_client(),
        episodic_memory=episodic_memory, session_id=TEST_SESSION_ID,
    )

    await summarizer.flush()

    episodic_memory.write.assert_called_once()
    call_kwargs = episodic_memory.write.call_args.kwargs
    assert call_kwargs["agent"] == agent_state.active
    assert call_kwargs["session_id"] == TEST_SESSION_ID
    assert call_kwargs["reason"] == "session_end_raw"
    assert call_kwargs["span_turns"] == 2
    assert call_kwargs["messages"] == messages[1:]
    assert call_kwargs["summary"].startswith(UNSUMMARIZED_MARKER)
    assert "how do I deploy this?" in call_kwargs["summary"]
    assert "run the deploy script" in call_kwargs["summary"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_flush_with_nothing_but_system_message_does_not_write():
    messages = [{"role": "system", "content": "sys"}]
    episodic_memory = make_episodic_memory()
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=ContextMeter(context_limit=1000),
        panel=MagicMock(), client=make_openai_client(),
        episodic_memory=episodic_memory, session_id=TEST_SESSION_ID,
    )

    await summarizer.flush()

    episodic_memory.write.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_flush_archives_everything_regardless_of_keep_recent():
    messages = [
        {"role": "system", "content": "sys"},
        *[{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)],
    ]
    episodic_memory = make_episodic_memory()
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=ContextMeter(context_limit=1000),
        panel=MagicMock(), client=make_openai_client(),
        episodic_memory=episodic_memory, session_id=TEST_SESSION_ID,
    )
    summarizer._keep_recent = 4  # must not limit what flush() archives

    await summarizer.flush()

    assert episodic_memory.write.call_args.kwargs["messages"] == messages[1:]
    assert episodic_memory.write.call_args.kwargs["span_turns"] == 10


@pytest.mark.unit
@pytest.mark.asyncio
async def test_flush_never_calls_the_llm():
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    client = make_openai_client()
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=ContextMeter(context_limit=1000),
        panel=MagicMock(), client=client,
        episodic_memory=make_episodic_memory(), session_id=TEST_SESSION_ID,
    )

    await summarizer.flush()

    client.chat.completions.create.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_flush_failure_does_not_raise():
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    episodic_memory = MagicMock()
    episodic_memory.write.side_effect = RuntimeError("disk full")
    summarizer = ContextSummarizer(
        context=make_context(messages), meter=ContextMeter(context_limit=1000),
        panel=MagicMock(), client=make_openai_client(),
        episodic_memory=episodic_memory, session_id=TEST_SESSION_ID,
    )

    await summarizer.flush()  # must not raise


# ─── upgrade_pending_episodes() — startup re-summarization pass ───


def make_pending_episode(episode_id: str, agent: str = "hope") -> SimpleNamespace:
    return SimpleNamespace(
        id=episode_id,
        agent=agent,
        messages=[
            SimpleNamespace(role="user", content_text="how do I deploy this?"),
            SimpleNamespace(role="assistant", content_text="run the deploy script"),
        ],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upgrade_pending_episodes_upgrades_each_one():
    episodic_memory = MagicMock()
    episodic_memory.list_by_reason.return_value = [make_pending_episode("ep_1")]
    client = make_openai_client("a real summary")

    await upgrade_pending_episodes(episodic_memory, client)

    episodic_memory.list_by_reason.assert_called_once_with("session_end_raw")
    episodic_memory.upgrade.assert_called_once_with("ep_1", "hope", "a real summary")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upgrade_pending_episodes_with_none_pending_does_nothing():
    episodic_memory = MagicMock()
    episodic_memory.list_by_reason.return_value = []
    client = make_openai_client()

    await upgrade_pending_episodes(episodic_memory, client)

    client.chat.completions.create.assert_not_called()
    episodic_memory.upgrade.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upgrade_pending_episodes_one_failure_does_not_block_the_rest():
    episodic_memory = MagicMock()
    episodic_memory.list_by_reason.return_value = [
        make_pending_episode("ep_broken"),
        make_pending_episode("ep_fine"),
    ]
    client = make_openai_client("a real summary")
    client.chat.completions.create = AsyncMock(
        side_effect=[RuntimeError("api down"), client.chat.completions.create.return_value]
    )

    await upgrade_pending_episodes(episodic_memory, client)  # must not raise

    episodic_memory.upgrade.assert_called_once_with("ep_fine", "hope", "a real summary")


# ─── inject_warm_start() — session warm-start ─────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_inject_warm_start_adds_last_session_summary_to_context():
    episodic_memory = MagicMock()
    episodic_memory.get_latest_by_reason.return_value = SimpleNamespace(
        summary="Pavan and HOPE discussed the deployment pipeline."
    )
    context = MagicMock()

    await inject_warm_start(episodic_memory, context, agent="hope")

    episodic_memory.get_latest_by_reason.assert_called_once_with("session_end", "hope")
    context.add_message.assert_called_once()
    added = context.add_message.call_args[0][0]
    assert added["role"] == "developer"
    assert "Pavan and HOPE discussed the deployment pipeline." in added["content"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_inject_warm_start_with_no_prior_session_does_nothing():
    episodic_memory = MagicMock()
    episodic_memory.get_latest_by_reason.return_value = None
    context = MagicMock()

    await inject_warm_start(episodic_memory, context, agent="hope")

    context.add_message.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_inject_warm_start_lookup_failure_does_not_raise_or_add_message():
    episodic_memory = MagicMock()
    episodic_memory.get_latest_by_reason.side_effect = RuntimeError("db is locked")
    context = MagicMock()

    await inject_warm_start(episodic_memory, context, agent="hope")  # must not raise

    context.add_message.assert_not_called()

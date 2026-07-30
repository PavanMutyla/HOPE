"""
Shared test fixtures for the HOPE test suite.

Every fixture here uses fakes/mocks so the full suite runs
without real API keys, audio hardware, or network access.
"""

import hashlib
import os
from unittest.mock import AsyncMock, MagicMock

import pytest


def pytest_configure(config):
    """
    Force fake env vars before any module is imported, overriding whatever is
    already in os.environ (e.g. a real .env auto-loaded by an IDE's debug
    session). settings.py's `settings` singleton is built once at first
    import, so if a real value leaks into os.environ ahead of this hook,
    setdefault() would be a no-op and no later monkeypatch could undo it.
    Live tests (test_*_live.py) intentionally bypass this by reading the
    real key straight from .env via dotenv_values, so overriding here is safe.
    When a new required key is added to settings.py, add it here too — tests
    will fail loudly if this list drifts from the real Settings class.
    """
    defaults = {
        "OPENAI_API_KEY": "test-openai-key-not-real",
        "CARTESIA_API_KEY": "test-cartesia-key-not-real",
        "CARTESIA_VOICE_ID": "test-cartesia-voice-id",
        "USER_NAME": "TestUser",
        "LOG_LEVEL": "INFO",
        "STT_MODEL": "whisper-1",
        "LLM_MODEL": "gpt-4o",
        "LLM_PROVIDER": "openai",
        "LANGFUSE_PUBLIC_KEY": "test-langfuse-pk",
        "LANGFUSE_SECRET_KEY": "test-langfuse-sk",
        "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        "ATLAS_LLM_MODEL": "gpt-4o-mini",
        "ATLAS_WORKSPACE": "/tmp/test-atlas-workspace",
        "ATLAS_VOICE_ID": "test-atlas-voice-id",
        "KOKORO_VOICE_ID": "af_heart",
        "KOKORO_ATLAS_VOICE_ID": "af_bella",
    }
    for key, value in defaults.items():
        os.environ[key] = value


# ─── Fake environment ───────────────────────────────────────────

@pytest.fixture
def fake_env(monkeypatch):
    """
    Injects all required settings as fake values so Settings() loads cleanly.
    Use this in any test that constructs a fresh Settings(_env_file=None).
    Add new required keys here whenever settings.py grows — a missing key
    will surface as a ValidationError, which is the intended failure mode.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-not-real")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia-key-not-real")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "test-cartesia-voice-id")
    monkeypatch.setenv("USER_NAME", "TestUser")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("STT_MODEL", "whisper-1")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test-langfuse-pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "test-langfuse-sk")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    monkeypatch.setenv("ATLAS_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("ATLAS_WORKSPACE", "/tmp/test-atlas-workspace")
    monkeypatch.setenv("ATLAS_VOICE_ID", "test-atlas-voice-id")
    monkeypatch.setenv("KOKORO_VOICE_ID", "af_heart")
    monkeypatch.setenv("KOKORO_ATLAS_VOICE_ID", "af_bella")


# ─── Voice agent fixtures ────────────────────────────────────────

@pytest.fixture
def hope_voice_agent():
    from core.voice.agent import VoiceAgent
    return VoiceAgent(name="hope", system_prompt="You are HOPE.", voice_id="hope-v1")


@pytest.fixture
def atlas_voice_agent():
    from core.voice.agent import VoiceAgent
    return VoiceAgent(name="atlas", system_prompt="You are Atlas.", voice_id="atlas-v2")


@pytest.fixture
def agent_registry(hope_voice_agent, atlas_voice_agent):
    from core.voice.agent import AgentRegistry
    registry = AgentRegistry()
    registry.register(hope_voice_agent)
    registry.register(atlas_voice_agent)
    return registry


# ─── Mock pipeline services ──────────────────────────────────────

@pytest.fixture
def mock_llm_service():
    """Mock LLM service — stands in for OpenAILLMService or any future provider."""
    svc = AsyncMock()
    svc.register_function = MagicMock()
    svc.push_frame = AsyncMock()
    return svc


@pytest.fixture
def mock_pipeline_bundle(mock_llm_service):
    """
    Mock VoicePipelineBundle for tests that need wiring but not real pipeline construction.
    The llm field is a real AsyncMock so push_frame calls can be asserted.
    """
    bundle = MagicMock()
    bundle.llm = mock_llm_service
    bundle.context = MagicMock()
    bundle.context.messages = [{"role": "system", "content": "You are HOPE."}]
    return bundle


@pytest.fixture
def pipeline_mocks(monkeypatch):
    """
    Patches all external service constructors in core.voice.pipeline so
    build_pipeline() can be called without API keys, audio hardware, or ML models.
    Returns a dict of {name: mock_instance} for per-test assertions.
    """
    import core.voice.pipeline as pm

    mocks = {name: MagicMock() for name in [
        "LocalAudioTransport",
        "OpenAISTTService",
        "OpenAILLMService",
        "KokoroTTSService",
        "SileroVADAnalyzer",
        "LocalSmartTurnAnalyzerV3",
        "LangfuseTracer",
        "LangfuseObserver",
        "Pipeline",
        "PipelineWorker",
        "StatusPanel",
        "StatusMonitor",
        "ContextSummarizer",
        "AsyncOpenAI",
        "EpisodicMemory",
        "SemanticMemory",
    ]}

    for name, mock in mocks.items():
        monkeypatch.setattr(pm, name, mock)

    return mocks


# ─── Orchestrator fixture ────────────────────────────────────────

@pytest.fixture
def mock_orchestrator(agent_registry, mock_pipeline_bundle, monkeypatch):
    """VoiceOrchestrator backed by real registry + mock bundle. AsyncOpenAI is patched out."""
    import core.voice.orchestrator as om
    monkeypatch.setattr(om, "AsyncOpenAI", MagicMock())
    from core.voice.orchestrator import VoiceOrchestrator
    return VoiceOrchestrator(agent_registry, mock_pipeline_bundle)


# ─── Episodic memory fixtures ────────────────────────────────────

@pytest.fixture
def fake_embedding_function():
    """Deterministic, offline stand-in for Chroma's default embedding model —
    keeps episodic-memory tests fast and network-free instead of downloading/
    running a real ONNX model. Must subclass chromadb.EmbeddingFunction (not
    just duck-type __call__) to inherit the default embed_query() Chroma's
    query path requires.

    Bag-of-words hashing (not a length/checksum scalar pair): each word hashes
    into one of 256 buckets and increments a count, so texts with genuinely
    different vocabulary land in genuinely different vectors. A cruder fake
    (e.g. keyed only on text length, or too few buckets) collides too easily
    and makes nearest-neighbor assertions in tests flaky/wrong. Uses
    hashlib (not the builtin `hash()`, which is salted per-process) so the
    same word always maps to the same bucket across separate test runs.
    """
    chromadb = pytest.importorskip("chromadb")

    class FakeEmbeddingFunction(chromadb.EmbeddingFunction):
        _DIMENSIONS = 256

        def __init__(self):
            pass

        def __call__(self, input):
            vectors = []
            for text in input:
                vector = [0.0] * self._DIMENSIONS
                for word in text.lower().split():
                    bucket = int(hashlib.sha256(word.encode()).hexdigest(), 16) % self._DIMENSIONS
                    vector[bucket] += 1.0
                vectors.append(vector)
            return vectors

        @staticmethod
        def name():
            return "fake-embedding-function"

        def get_config(self):
            return {}

        @staticmethod
        def build_from_config(config):
            return FakeEmbeddingFunction()

    return FakeEmbeddingFunction()

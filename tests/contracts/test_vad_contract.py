"""
Contract tests for VAD (Voice Activity Detection) providers.

VAD analyzers are NOT pipecat FrameProcessors — they are audio analyzers
passed to LLMUserAggregatorParams. The contract is different: they must
expose analyze_audio, voice_confidence, and no API key requirement.
"""

import inspect
import pytest


class VADContractBase:
    """Check the class interface directly to avoid model-load side effects in CI."""

    def get_class(self):
        raise NotImplementedError

    def test_has_analyze_audio(self):
        cls = self.get_class()
        assert hasattr(cls, "analyze_audio"), "VAD must have analyze_audio method"

    def test_has_voice_confidence(self):
        cls = self.get_class()
        assert hasattr(cls, "voice_confidence"), "VAD must expose voice_confidence"

    def test_requires_no_api_credentials(self):
        """VAD is a local model — constructor must not require an API key."""
        cls = self.get_class()
        sig = inspect.signature(cls.__init__)
        param_names = list(sig.parameters.keys())
        assert "api_key" not in param_names, "VAD should not require an API key"


class TestSileroVADContract(VADContractBase):
    """Silero VAD — the current local VAD provider."""

    def get_class(self):
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        return SileroVADAnalyzer

    @pytest.mark.contract
    def test_has_analyze_audio(self):
        super().test_has_analyze_audio()

    @pytest.mark.contract
    def test_has_voice_confidence(self):
        super().test_has_voice_confidence()

    @pytest.mark.contract
    def test_requires_no_api_credentials(self):
        super().test_requires_no_api_credentials()


# Future:
# class TestWebRTCVADContract(VADContractBase): ...

"""
Contract tests for TTS (Text-to-Speech) providers.

Any TTS service must satisfy this interface so it can be swapped
(Cartesia → ElevenLabs, PlayHT, etc.) by changing one import.
"""

import inspect
import pytest


class TTSContractBase:
    def create_service(self):
        raise NotImplementedError

    def test_has_process_frame(self):
        svc = self.create_service()
        assert hasattr(svc, "process_frame"), "TTS service must have process_frame method"
        assert callable(svc.process_frame)

    def test_process_frame_is_async(self):
        svc = self.create_service()
        assert inspect.iscoroutinefunction(svc.process_frame)

    def test_has_start_method(self):
        svc = self.create_service()
        assert hasattr(svc, "start")

    def test_accepts_voice_configuration(self):
        """TTS provider must accept a voice/model at construction time."""
        svc = self.create_service()
        assert svc is not None


class TestCartesiaTTSContract(TTSContractBase):
    """Cartesia — the current production TTS provider."""

    def create_service(self):
        from pipecat.services.cartesia.tts import CartesiaTTSService
        return CartesiaTTSService(
            api_key="fake-key-for-contract-test",
            settings=CartesiaTTSService.Settings(voice="fake-voice-id"),
        )

    @pytest.mark.contract
    def test_has_process_frame(self):
        super().test_has_process_frame()

    @pytest.mark.contract
    def test_process_frame_is_async(self):
        super().test_process_frame_is_async()

    @pytest.mark.contract
    def test_has_start_method(self):
        super().test_has_start_method()

    @pytest.mark.contract
    def test_accepts_voice_configuration(self):
        super().test_accepts_voice_configuration()


# Future:
# class TestElevenLabsTTSContract(TTSContractBase): ...

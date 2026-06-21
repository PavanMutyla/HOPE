"""
Contract tests for TTS (Text-to-Speech) providers.

Any TTS service must satisfy this interface so it can be swapped
(Kokoro, Cartesia, ElevenLabs, etc.) by changing one import.
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


class TestKokoroTTSContract(TTSContractBase):
    """Kokoro — the current production TTS provider (local, no API key)."""

    def create_service(self):
        from pipecat.services.kokoro.tts import KokoroTTSService
        return KokoroTTSService(
            settings=KokoroTTSService.Settings(voice="af_heart"),
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

    @pytest.mark.contract
    def test_has_run_tts_method(self):
        svc = self.create_service()
        assert hasattr(svc, "run_tts"), "KokoroTTSService must expose run_tts for audio generation"
        assert inspect.isasyncgenfunction(svc.run_tts)

    @pytest.mark.contract
    def test_settings_class_accepts_voice(self):
        from pipecat.services.kokoro.tts import KokoroTTSService
        s = KokoroTTSService.Settings(voice="am_puck")
        assert s.voice == "am_puck"


class TestCartesiaTTSContract(TTSContractBase):
    """Cartesia — kept alongside Kokoro as a fallback provider."""

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

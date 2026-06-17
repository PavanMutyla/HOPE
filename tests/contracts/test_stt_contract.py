"""
Contract tests for STT (Speech-to-Text) providers.

Any STT service must satisfy this interface so it can be swapped
(OpenAI Whisper → Deepgram, AssemblyAI, etc.) by changing one import.
"""

import inspect
import pytest


class STTContractBase:
    def create_service(self):
        raise NotImplementedError

    def test_has_process_frame(self):
        svc = self.create_service()
        assert hasattr(svc, "process_frame"), "STT service must have process_frame method"
        assert callable(svc.process_frame)

    def test_process_frame_is_async(self):
        svc = self.create_service()
        assert inspect.iscoroutinefunction(svc.process_frame)

    def test_has_start_method(self):
        svc = self.create_service()
        assert hasattr(svc, "start")


class TestOpenAISTTContract(STTContractBase):
    """OpenAI Whisper — the current production STT provider."""

    def create_service(self):
        from pipecat.services.openai.stt import OpenAISTTService
        return OpenAISTTService(
            api_key="fake-key-for-contract-test",
            settings=OpenAISTTService.Settings(model="whisper-1", language="en"),
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


# Future:
# class TestDeepgramSTTContract(STTContractBase): ...

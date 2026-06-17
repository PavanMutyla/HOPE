"""
Contract tests for LLM providers.

Any LLM service used in HOPE must satisfy this interface so it can
be swapped (OpenAI → Ollama, Anthropic, etc.) by changing one import.
Add a new subclass of LLMContractBase for each provider you add.
"""

import inspect
import pytest


class LLMContractBase:
    """
    Base contract. Subclass and implement create_service() for each LLM provider.
    The service is constructed with fake credentials — no real API calls are made.
    """

    def create_service(self):
        raise NotImplementedError

    def test_has_process_frame(self):
        svc = self.create_service()
        assert hasattr(svc, "process_frame"), "LLM service must have process_frame method"
        assert callable(svc.process_frame)

    def test_process_frame_is_async(self):
        svc = self.create_service()
        assert inspect.iscoroutinefunction(svc.process_frame), (
            "process_frame must be async — pipecat pipelines are async"
        )

    def test_has_start_method(self):
        svc = self.create_service()
        assert hasattr(svc, "start"), "LLM service must have a start method (pipecat lifecycle)"

    def test_can_register_function(self):
        svc = self.create_service()
        assert hasattr(svc, "register_function"), (
            "LLM service must support register_function for tool/function calling"
        )


class TestOpenAILLMContract(LLMContractBase):
    """OpenAI GPT-4o — the current production LLM provider."""

    def create_service(self):
        from pipecat.services.openai.llm import OpenAILLMService
        return OpenAILLMService(
            api_key="fake-key-for-contract-test",
            settings=OpenAILLMService.Settings(model="gpt-4o"),
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
    def test_can_register_function(self):
        super().test_can_register_function()


# Future providers — uncomment and implement create_service() when added:
#
# class TestOllamaLLMContract(LLMContractBase):
#     def create_service(self):
#         from pipecat.services.ollama.llm import OllamaLLMService
#         return OllamaLLMService(model="llama3", base_url="http://localhost:11434")
#
#     @pytest.mark.contract
#     def test_has_process_frame(self): super().test_has_process_frame()
#     @pytest.mark.contract
#     def test_process_frame_is_async(self): super().test_process_frame_is_async()
#     @pytest.mark.contract
#     def test_has_run_method(self): super().test_has_run_method()
#     @pytest.mark.contract
#     def test_can_register_function(self): super().test_can_register_function()

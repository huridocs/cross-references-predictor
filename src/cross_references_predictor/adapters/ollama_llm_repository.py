import ollama

from cross_references_predictor.configuration import OLLAMA_HOST, OLLAMA_MODEL
from cross_references_predictor.ports.llm_service import LLMService


class OllamaLLMRepository(LLMService):
    def __init__(self, host: str | None = None, model: str | None = None):
        self.host = host or OLLAMA_HOST
        self.model = model or OLLAMA_MODEL
        self._client = ollama.Client(host=self.host)

    def query(self, prompt: str, system_prompt: str = "", think: bool = False) -> str:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, think=think)

    def chat(self, messages: list[dict], think: bool = False) -> str:
        response = self._client.chat(model=self.model, messages=messages, think=think)
        content = response.message.content
        return content if content else ""

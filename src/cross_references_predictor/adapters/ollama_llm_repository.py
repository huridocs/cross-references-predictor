import logging
import time

import ollama

from cross_references_predictor.configuration import OLLAMA_HOST, OLLAMA_MODEL
from cross_references_predictor.ports.llm_service import LLMService

logger = logging.getLogger(__name__)


class OllamaLLMRepository(LLMService):
    def __init__(self, host: str | None = None, model: str | None = None, max_retries: int = 5):
        self.host = host or OLLAMA_HOST
        self.model = model or OLLAMA_MODEL
        self._client = ollama.Client(host=self.host)
        self._max_retries = max_retries

    def query(self, prompt: str, system_prompt: str = "", think: bool = False) -> str:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, think=think)

    def chat(self, messages: list[dict], think: bool = False) -> str:
        for attempt in range(self._max_retries):
            try:
                response = self._client.chat(model=self.model, messages=messages, think=think)
                content = response.message.content
                return content if content else ""
            except Exception as e:
                if attempt == self._max_retries - 1:
                    raise
                wait = 2**attempt
                logger.warning(
                    "Ollama request failed (attempt %d/%d): %s. Retrying in %ds...",
                    attempt + 1,
                    self._max_retries,
                    e,
                    wait,
                )
                time.sleep(wait)

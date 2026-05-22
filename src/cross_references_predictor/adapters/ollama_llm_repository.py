import logging
import os
import time

import httpx
from dotenv import load_dotenv

from cross_references_predictor.configuration import OLLAMA_MODEL
from cross_references_predictor.ports.llm_service import LLMService

load_dotenv()

logger = logging.getLogger(__name__)


class OllamaLLMRepository(LLMService):
    def __init__(self, model: str | None = None, max_retries: int = 5, timeout: float = 120.0):
        api_key = os.getenv("OLLAMA_API_KEY")
        if not api_key:
            raise ValueError("OLLAMA_API_KEY is not set in .env. " "Get one from https://ollama.com/settings/api-keys")
        self.model = model or OLLAMA_MODEL
        self._client = httpx.Client(
            base_url="https://ollama.com/api",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self._max_retries = max_retries

    def query(self, prompt: str, system_prompt: str = "", think: bool = False) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if think:
            payload["think"] = True
        for attempt in range(self._max_retries):
            try:
                resp = self._client.post("/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
            except Exception as e:
                if attempt == self._max_retries - 1:
                    raise
                wait = 2**attempt
                logger.warning(
                    "Ollama Cloud API request failed (attempt %d/%d): %s. Retrying in %ds...",
                    attempt + 1,
                    self._max_retries,
                    e,
                    wait,
                )
                time.sleep(wait)

    def chat(self, messages: list[dict], think: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if think:
            payload["think"] = True
        for attempt in range(self._max_retries):
            try:
                resp = self._client.post("/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
            except Exception as e:
                if attempt == self._max_retries - 1:
                    raise
                wait = 2**attempt
                logger.warning(
                    "Ollama Cloud API request failed (attempt %d/%d): %s. Retrying in %ds...",
                    attempt + 1,
                    self._max_retries,
                    e,
                    wait,
                )
                time.sleep(wait)

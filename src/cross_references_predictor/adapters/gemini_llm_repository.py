from google import genai
from google.genai import types

from cross_references_predictor.configuration import GEMINI_API_KEY, GEMINI_MODEL
from cross_references_predictor.ports.llm_service import LLMService


class GeminiLLMRepository(LLMService):
    """Adapter for querying an LLM via the Gemini API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        self._client = genai.Client(api_key=self.api_key)

    def query(self, prompt: str, system_prompt: str = "", think: bool = False) -> str:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, think=think)

    def chat(self, messages: list[dict], think: bool = False) -> str:
        thinking_config = None
        if not think:
            thinking_config = types.ThinkingConfig(thinking_budget=0)

        config = (
            types.GenerateContentConfig(
                thinking_config=thinking_config,
            )
            if thinking_config
            else None
        )

        response = self._client.models.generate_content(
            model=self.model,
            contents=[types.Content(role=msg["role"], parts=[types.Part(text=msg["content"])]) for msg in messages],
            config=config,
        )
        return response.text if response and response.text else ""

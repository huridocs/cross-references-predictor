from abc import ABC, abstractmethod


class LLMService(ABC):
    """Port for querying Large Language Models.

    Implementations may use Ollama, OpenRouter, Gemini, or any other LLM provider.
    """

    @abstractmethod
    def query(self, prompt: str, system_prompt: str = "", think: bool = False) -> str:
        """Send a single prompt to the LLM and return the response text.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system-level instructions.
            think: Whether to include the model's reasoning/thinking in the response.

        Returns:
            The text content of the LLM response.
        """
        pass

    @abstractmethod
    def chat(self, messages: list[dict], think: bool = False) -> str:
        """Send a list of messages (conversation) to the LLM and return the response text.

        Args:
            messages: A list of message dicts, each with 'role' and 'content' keys.
            think: Whether to include the model's reasoning/thinking in the response.

        Returns:
            The text content of the LLM response.
        """
        pass

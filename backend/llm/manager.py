import anthropic
from config import get_settings


class LLMManager:
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete(self, model: str, system: str, user: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """Synchronous completion. Returns the text content of the first block."""
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    async def complete_async(self, model: str, system: str, user: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """Async completion using httpx-based async client."""
        async_client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
        message = await async_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

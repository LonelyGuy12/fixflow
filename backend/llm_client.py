"""
LLM Client for GLM 5.1 via Z.ai API (OpenAI-compatible endpoint).
"""
import time
import logging
from typing import Iterator, List, Dict, Any, Optional
import openai
from backend.config import GLM_API_KEY, GLM_BASE_URL, GLM_MODEL, LOG_LLM_CALLS

logger = logging.getLogger(__name__)


class GLMClient:
    """OpenAI-compatible wrapper for Z.ai's GLM models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = GLM_BASE_URL,
        model: str = GLM_MODEL,
    ):
        self.api_key = api_key or GLM_API_KEY
        self.base_url = base_url
        self.model = model
        self._client: Optional[openai.OpenAI] = None

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "GLM API key is not set. Please provide it in the sidebar or .env file."
                )
            self._client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Synchronous chat completion. Returns the full response string."""
        client = self._get_client()
        start = time.time()

        if LOG_LLM_CALLS:
            logger.info(
                "[GLM] chat() | model=%s | messages=%d | temp=%.1f",
                self.model, len(messages), temperature,
            )

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        elapsed = time.time() - start

        if LOG_LLM_CALLS:
            logger.info("[GLM] completed in %.2fs | output_chars=%d", elapsed, len(content))

        return content

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Streaming chat completion. Yields text chunks as they arrive."""
        client = self._get_client()

        if LOG_LLM_CALLS:
            logger.info(
                "[GLM] chat_stream() | model=%s | messages=%d",
                self.model, len(messages),
            )

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    def update_api_key(self, api_key: str) -> None:
        """Allow hot-swapping the API key (e.g. from Streamlit sidebar)."""
        self.api_key = api_key
        self._client = None  # Force re-initialization

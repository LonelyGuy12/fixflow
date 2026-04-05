"""
LLM Client for GLM 5.1 via Z.ai API (OpenAI-compatible endpoint).
Includes automatic retry with exponential backoff for rate-limit (429) errors.
"""
import time
import logging
import random
from typing import Iterator, List, Dict, Any, Optional
import openai
from backend.config import GLM_API_KEY, GLM_BASE_URL, GLM_MODEL, LOG_LLM_CALLS

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
INITIAL_BACKOFF = 5  # seconds


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

    def _backoff_wait(self, attempt: int) -> None:
        """Exponential backoff with jitter. Waits and logs the wait time."""
        wait = INITIAL_BACKOFF * (2 ** attempt) + random.uniform(0, 2)
        logger.warning("[GLM] Rate limited (429). Retrying in %.1fs (attempt %d/%d)...", wait, attempt + 1, MAX_RETRIES)
        time.sleep(wait)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Synchronous chat completion with automatic retry on 429."""
        client = self._get_client()
        start = time.time()

        if LOG_LLM_CALLS:
            logger.info(
                "[GLM] chat() | model=%s | messages=%d | temp=%.1f",
                self.model, len(messages), temperature,
            )

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
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

            except openai.RateLimitError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    self._backoff_wait(attempt)
                else:
                    raise RuntimeError(
                        f"GLM API rate limit exceeded after {MAX_RETRIES} retries. "
                        f"Please wait a moment and try again. Detail: {e}"
                    ) from e
            except openai.APIError as e:
                raise RuntimeError(f"GLM API error: {e}") from e

        raise RuntimeError(f"GLM request failed after {MAX_RETRIES} attempts: {last_error}")

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Streaming chat completion with automatic retry on 429."""
        client = self._get_client()

        if LOG_LLM_CALLS:
            logger.info(
                "[GLM] chat_stream() | model=%s | messages=%d",
                self.model, len(messages),
            )

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
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
                return  # Completed successfully

            except openai.RateLimitError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    self._backoff_wait(attempt)
                else:
                    raise RuntimeError(
                        f"GLM API rate limit exceeded after {MAX_RETRIES} retries. "
                        f"Please wait a moment and try again. Detail: {e}"
                    ) from e
            except openai.APIError as e:
                raise RuntimeError(f"GLM API error: {e}") from e

        raise RuntimeError(f"GLM stream failed after {MAX_RETRIES} attempts: {last_error}")

    def update_api_key(self, api_key: str) -> None:
        """Allow hot-swapping the API key (e.g. from Streamlit sidebar)."""
        self.api_key = api_key
        self._client = None  # Force re-initialization


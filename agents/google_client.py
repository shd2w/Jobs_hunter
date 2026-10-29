"""Optional Google AI client, using one authorized account within its quotas."""

import logging
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class GoogleAIResponse:
    """Response from Google AI Studio."""
    content: str
    model_used: str
    success: bool = True
    error: str = ""
    latency_ms: int = 0


class GoogleAIClient:
    """Client for Google AI Studio (Gemma models).

    Supports multiple API keys for automatic rotation on rate limits.
    Keys are loaded from env vars matching GOOGLE_AI_API_KEY* pattern
    (e.g. GOOGLE_AI_API_KEY, GOOGLE_AI_API_KEY2, GOOGLE_AI_API_KEY3).
    """

    def __init__(
        self,
        api_key: str | None = None,
        models: list[str] | None = None,
    ):
        # 26b is more reliable; 31b has intermittent 500s
        self.models = models or self._load_google_models()

        # Lazy import to avoid crash if not installed
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai not installed. Run: pip install google-genai"
            )

        # Build list of API keys and a genai.Client for each
        if api_key:
            # Explicit key passed — single-key mode
            self._api_keys = [api_key]
        else:
            self._api_keys = self._load_api_keys()

        if not self._api_keys:
            raise ValueError(
                "No Google AI API keys found. "
                "Set GOOGLE_AI_API_KEY (and optionally GOOGLE_AI_API_KEY2, etc.) in .env"
            )

        self._clients = [genai.Client(api_key=k) for k in self._api_keys]
        self._current_key_idx = 0

        logger.info(
            "GoogleAIClient initialised with %d API key(s), starting on key[0]",
            len(self._clients),
        )

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_api_keys() -> list[str]:
        """Load all env vars matching GOOGLE_AI_API_KEY* and return their values."""
        keys: list[str] = []
        # Primary key (no suffix)
        primary = os.getenv("GOOGLE_AI_API_KEY")
        if primary:
            keys.append(primary)
        return keys

    @staticmethod
    def _load_google_models() -> list[str]:
        """Load Google model chain from profile.yml."""
        try:
            import yaml
            from pathlib import Path
            profile_path = Path("config/profile.yml")
            if profile_path.exists():
                with open(profile_path, "r", encoding="utf-8") as f:
                    profile = yaml.safe_load(f) or {}
                models = profile.get("evaluation", {}).get("google_models", [])
                if models:
                    return models
        except Exception:
            pass
        return ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemma-4-31b-it"]

    @property
    def client(self):
        """Return the currently-active genai.Client."""
        return self._clients[self._current_key_idx]

    def _rotate_key(self) -> bool:
        """Advance to the next API key. Returns True if a new key is available."""
        next_idx = (self._current_key_idx + 1) % len(self._clients)
        if next_idx == self._current_key_idx:
            return False  # only one key — nowhere to rotate
        self._current_key_idx = next_idx
        logger.info("Rotated to API key[%d]", self._current_key_idx)
        return True

    # ------------------------------------------------------------------
    # Core chat method
    # ------------------------------------------------------------------

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> GoogleAIResponse:
        """Send a chat request to Google AI Studio.

        Error-handling strategy:
          • 429 / RESOURCE_EXHAUSTED → stop; retry later under provider policy.
          • 500 / INTERNAL           → try the next model on the SAME client.
          • Other errors              → try the next model on the SAME client.

        All keys × all models are attempted before giving up.
        """
        from google.genai import types

        last_error = ""
        start_key_idx = self._current_key_idx
        keys_tried = 0

        while keys_tried < len(self._clients):
            for model in self.models:
                start = time.time()
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        ),
                    )

                    latency = int((time.time() - start) * 1000)

                    if not response.text:
                        last_error = "Empty response"
                        logger.warning(
                            "Google/%s (key[%d]): empty response, trying next...",
                            model, self._current_key_idx,
                        )
                        continue

                    # Log token usage if available
                    usage_meta = getattr(response, 'usage_metadata', None)
                    if usage_meta:
                        prompt_tokens = getattr(usage_meta, 'prompt_token_count', 0)
                        completion_tokens = getattr(usage_meta, 'candidates_token_count', 0)
                        total_tokens = getattr(usage_meta, 'total_token_count', 0)
                        logger.info(
                            "[Google/%s] key[%d] in=%s out=%s total=%s tokens, %dms",
                            model, self._current_key_idx,
                            prompt_tokens, completion_tokens, total_tokens,
                            latency,
                        )
                    else:
                        logger.info(
                            "[Google/%s] key[%d] %dms",
                            model, self._current_key_idx, latency,
                        )

                    return GoogleAIResponse(
                        content=response.text,
                        model_used=f"google/{model}",
                        success=True,
                        latency_ms=latency,
                    )

                except Exception as e:
                    latency = int((time.time() - start) * 1000)
                    error_message = str(e)
                    last_error = type(e).__name__

                    if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
                        logger.warning(
                            "Google/%s (key[%d]) rate-limited (%dms). "
                            "Stopping this provider call...",
                            model, self._current_key_idx, latency,
                        )
                        return GoogleAIResponse(content="", model_used=model, success=False,
                                                error="Google quota exhausted; retry later within provider policy")

                    if "500" in error_message or "INTERNAL" in error_message or "503" in error_message:
                        logger.warning(
                            "Google/%s (key[%d]) server error (%s), waiting 2s...",
                            model, self._current_key_idx, last_error[:60],
                        )
                        time.sleep(2)
                        continue

                    logger.warning(
                        "Google/%s (key[%d]) error: %s",
                        model, self._current_key_idx, last_error,
                    )
                    continue
            else:
                # Models loop completed without break → all models exhausted on
                # this key. Move to the next key.
                keys_tried += 1
                if keys_tried < len(self._clients):
                    self._rotate_key()
                continue

            # Reached here via 'break' (rate-limit rotation) — count and retry
            keys_tried += 1
            continue

        # Restore starting key index so next call begins where we left off
        self._current_key_idx = start_key_idx

        return GoogleAIResponse(
            content="",
            model_used="google/none",
            success=False,
            error=f"All Google keys/models exhausted. Last: {last_error}",
        )


def test_google_connection() -> bool:
    """Quick test that Google AI Studio is reachable."""
    try:
        client = GoogleAIClient()
        response = client.chat(
            system_prompt="You are a test assistant.",
            user_prompt="Reply with exactly: OK",
            max_tokens=10,
        )
        if response.success:
            logger.info("Google AI connection OK (model: %s)", response.model_used)
            return True
        else:
            logger.error("Google AI test failed: %s", response.error)
            return False
    except Exception as e:
        logger.error("Google AI connection error (%s)", type(e).__name__)
        return False

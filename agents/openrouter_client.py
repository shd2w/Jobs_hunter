"""
OpenRouter API client.

Provides an OpenAI-compatible wrapper for free models on OpenRouter.
Features:
- Automatic model fallback (primary → backup → fallback)
- Fail-closed rate-limit handling (no model hopping on quota exhaustion)
- Request/response logging
- Token usage tracking
"""

import logging
import os
import time
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT = 90  # seconds — free models can be slow


@dataclass
class ChatResponse:
    """Response from an OpenRouter chat completion."""
    content: str
    model_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    success: bool = True
    error: str = ""
    latency_ms: int = 0
    reasoning: str = ""
    reasoning_details: list | None = None


class OpenRouterClient:
    """Client for OpenRouter API with automatic model fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        models: list[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OpenRouter")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY in .env"
            )

        self.models = models or self._load_models_from_config() or [
            "nvidia/nemotron-3.5-super-vl:free",
            "openai/gpt-oss-120b:free",
            "google/gemma-4-31b-it:free",
            "deepseek/deepseek-v4-flash:free",
        ]
        self.timeout = timeout

        # Track usage
        self._total_requests = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0

    @staticmethod
    def _load_models_from_config() -> list[str]:
        try:
            import yaml
            from pathlib import Path
            profile_path = Path("config/profile.yml")
            if profile_path.exists():
                with open(profile_path, "r", encoding="utf-8") as f:
                    profile = yaml.safe_load(f) or {}
                models = profile.get("evaluation", {}).get("openrouter_models", [])
                if models:
                    return models
        except Exception:
            pass
        return []

        # Track usage
        self._total_requests = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        reasoning: bool = True,
        messages: list[dict] | None = None,
    ) -> ChatResponse:
        """Send a chat completion request with automatic model fallback.
        
        Tries model fallback for ordinary errors. Quota exhaustion stops this
        provider call immediately; the caller may retry later under policy.
        Supports reasoning-enabled models like nvidia/nemotron-3.5-super-vl:free.
        """
        last_error = ""

        for i, model in enumerate(self.models):
            try:
                response = self._request(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    reasoning=reasoning,
                    messages=messages,
                )
                if response.success:
                    self._total_requests += 1
                    self._total_prompt_tokens += response.prompt_tokens
                    self._total_completion_tokens += response.completion_tokens
                    return response
                else:
                    if "429" in response.error:
                        return response
                    last_error = response.error
                    logger.warning(
                        f"Model {model} failed: {response.error}. "
                        f"Trying next model..."
                    )
            except Exception as e:
                last_error = type(e).__name__
                logger.warning(
                    f"Model {model} exception: {type(e).__name__}. Trying next model..."
                )

            # Small delay before trying next model
            if i < len(self.models) - 1:
                time.sleep(1)

        # All models failed
        return ChatResponse(
            content="",
            model_used="none",
            success=False,
            error=f"All models failed. Last error: {last_error}",
        )

    def _request(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        reasoning: bool = True,
        messages: list[dict] | None = None,
    ) -> ChatResponse:
        """Make a single request to OpenRouter."""
        start = time.time()

        if messages is not None:
            req_messages = messages
        else:
            req_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        payload = {
            "model": model,
            "messages": req_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if reasoning:
            payload["reasoning"] = {"enabled": True}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/job-search-automation",
                    "X-Title": "Job Search Automation",
                },
                json=payload,
            )

        latency = int((time.time() - start) * 1000)

        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "unspecified")
            # Honor the provider policy by stopping, not by capping its wait.
            return ChatResponse(
                content="",
                model_used=model,
                success=False,
                error=f"Rate limited (429). Retry-After: {retry_after}s",
                latency_ms=latency,
            )

        if resp.status_code != 200:
            return ChatResponse(
                content="",
                model_used=model,
                success=False,
                error=f"Provider returned HTTP {resp.status_code}",
                latency_ms=latency,
            )

        data = resp.json()

        # Check for error in response body
        if "error" in data:
            return ChatResponse(
                content="",
                model_used=model,
                success=False,
                error="Provider returned an API error (body redacted)",
                latency_ms=latency,
            )

        # Extract content
        choices = data.get("choices", [])
        if not choices:
            return ChatResponse(
                content="",
                model_used=model,
                success=False,
                error="No choices in response",
                latency_ms=latency,
            )

        msg_obj = choices[0].get("message", {})
        content = msg_obj.get("content", "") or ""
        reasoning_text = msg_obj.get("reasoning", "") or ""
        reasoning_details = msg_obj.get("reasoning_details", None)
        usage = data.get("usage", {})

        logger.info(
            "[%s] %s->%s tokens, %dms",
            model,
            usage.get('prompt_tokens', '?'),
            usage.get('completion_tokens', '?'),
            latency,
        )

        return ChatResponse(
            content=content,
            model_used=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            success=True,
            latency_ms=latency,
            reasoning=reasoning_text,
            reasoning_details=reasoning_details,
        )

    @property
    def usage_stats(self) -> dict:
        """Return cumulative usage stats."""
        return {
            "total_requests": self._total_requests,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
        }


def test_connection() -> bool:
    """Quick test that OpenRouter is reachable and the API key works."""
    try:
        client = OpenRouterClient()
        response = client.chat(
            system_prompt="You are a test assistant.",
            user_prompt="Reply with exactly: OK",
            max_tokens=10,
        )
        if response.success:
            logger.info(f"OpenRouter connection OK (model: {response.model_used})")
            return True
        else:
            logger.error(f"OpenRouter test failed: {response.error}")
            return False
    except Exception as e:
        logger.error("OpenRouter connection failed (%s)", type(e).__name__)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing OpenRouter connection...")
    ok = test_connection()
    print(f"Result: {'✅ OK' if ok else '❌ FAILED'}")

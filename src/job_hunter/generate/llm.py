"""The only module that talks to a language model.

Everything goes through `complete()` so that retries, the call log, and provider
differences live in exactly one place. LiteLLM normalises the provider surface;
we normalise everything else.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import Settings, load_settings

#: Providers report these differently; we read whichever is present.
_TEXT_KEYS = ("content",)


class LLMError(RuntimeError):
    """A model call failed in a way the caller should surface to the user."""


@dataclass
class Completion:
    text: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def complete(
    prompt: str,
    *,
    system: str = "",
    settings: Settings | None = None,
    max_tokens: int | None = None,
    retries: int = 3,
) -> Completion:
    """Send one prompt, return the text.

    Retries transient failures with exponential backoff. Raises `LLMError` with
    a message meant for the user rather than a stack trace.
    """
    cfg = settings or load_settings()
    if (reason := cfg.missing()) is not None:
        raise LLMError(reason)

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "max_tokens": max_tokens or cfg.max_tokens,
        "timeout": cfg.request_timeout,
    }
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    if cfg.api_base:
        kwargs["api_base"] = cfg.api_base

    delay = 2.0
    last: Exception | None = None
    for attempt in range(retries):
        try:
            result = _call(kwargs)
            _log(cfg.call_log, prompt, result)
            return result
        except Exception as exc:  # LiteLLM raises a wide family of provider errors.
            last = exc
            if not _retryable(exc) or attempt == retries - 1:
                break
            time.sleep(delay)
            delay *= 2

    raise LLMError(f"Model call failed after {retries} attempt(s): {last}") from last


def _call(kwargs: dict[str, Any]) -> Completion:
    import litellm  # imported lazily: it is slow and not needed for offline use

    litellm.drop_params = True  # a model that rejects a param should not 400
    response = litellm.completion(**kwargs)
    data = response.model_dump() if hasattr(response, "model_dump") else dict(response)

    text = ""
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        for key in _TEXT_KEYS:
            if message.get(key):
                text = message[key]
                break

    usage = data.get("usage") or {}
    cost = 0.0
    try:
        cost = float(litellm.completion_cost(completion_response=response) or 0.0)
    except Exception:
        pass  # unknown pricing (local models, new releases) is not an error

    return Completion(
        text=(text or "").strip(),
        model=data.get("model", kwargs["model"]),
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        cost_usd=cost,
        raw=data,
    )


def _retryable(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    names = ("ratelimit", "timeout", "overloaded", "unavailable", "internalserver", "apiconnection")
    phrases = ("rate limit", "overloaded", "timed out", "503", "529")
    return any(n in name for n in names) or any(p in text for p in phrases)


def _log(path: Path, prompt: str, result: Completion) -> None:
    """Append one line per call so users can audit spend. Never fatal."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": round(result.cost_usd, 6),
            "prompt_chars": len(prompt),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass

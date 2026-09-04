"""Runtime settings, read from the environment.

Users bring their own model and key. Any provider LiteLLM supports works, which
includes local Ollama models, so the tool is usable with no paid account.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .profile.store import DEFAULT_DIR

#: Sensible default: strong enough for CV writing, and a model most users can reach.
DEFAULT_MODEL = "anthropic/claude-sonnet-5"


@dataclass(frozen=True)
class Settings:
    model: str = DEFAULT_MODEL
    api_key: str = ""
    #: LiteLLM talks to Ollama and other self-hosted servers through this.
    api_base: str = ""
    home: Path = DEFAULT_DIR
    #: Hard ceiling per generation, guarding against a runaway prompt.
    max_tokens: int = 8000
    request_timeout: int = 180

    @property
    def output_dir(self) -> Path:
        return self.home / "output"

    @property
    def call_log(self) -> Path:
        return self.home / "llm_calls.jsonl"

    @property
    def is_local(self) -> bool:
        """Local models need no key, so the UI should not nag for one."""
        return self.model.startswith(("ollama/", "ollama_chat/")) or bool(self.api_base)

    def missing(self) -> str | None:
        """Human-readable reason the tool cannot call a model yet, if any."""
        if not self.model:
            return "No model set. Set JOB_HUNTER_MODEL, e.g. anthropic/claude-sonnet-5."
        if not self.api_key and not self.is_local:
            return (
                f"No API key for {self.model!r}. Set JOB_HUNTER_API_KEY, or point "
                "JOB_HUNTER_MODEL at a local model such as ollama/llama3.1."
            )
        return None


def load_settings() -> Settings:
    home = os.environ.get("JOB_HUNTER_HOME")
    return Settings(
        model=os.environ.get("JOB_HUNTER_MODEL", DEFAULT_MODEL),
        api_key=os.environ.get("JOB_HUNTER_API_KEY", ""),
        api_base=os.environ.get("JOB_HUNTER_API_BASE", ""),
        home=Path(home) if home else DEFAULT_DIR,
    )

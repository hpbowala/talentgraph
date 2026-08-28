"""Single point of access to the OpenAI API.

All agent and ingestion code talks to `LLMProvider`, never to the OpenAI SDK
directly, so the model/provider can change without touching agent logic.
Structured-output calls are cached on disk keyed by (model, prompts, schema) so
repeated ingestion runs during development cost nothing.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "gpt-5-mini"


class LLMProvider:
    def __init__(self, model: str | None = None, cache_dir: str | Path | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.cache_dir = Path(cache_dir or os.getenv("LLM_CACHE_DIR", ".cache/llm"))
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI()
        return self._client

    def parse(self, *, system: str, user: str, schema: type[T], use_cache: bool = True) -> T:
        """Structured-output call returning a validated instance of `schema`."""
        cache_file = self._cache_path(system, user, schema.__name__)
        if use_cache and cache_file.exists():
            return schema.model_validate_json(cache_file.read_text(encoding="utf-8"))

        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=schema,
        )
        result = response.output_parsed
        if result is None:
            raise RuntimeError(f"Model returned no parsed output for schema {schema.__name__}")
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(result.model_dump_json(), encoding="utf-8")
        return result

    def complete(self, *, system: str, user: str) -> str:
        """Plain-text completion (used for final answer synthesis)."""
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.output_text

    def _cache_path(self, system: str, user: str, schema_name: str) -> Path:
        key = hashlib.sha256(
            json.dumps([self.model, system, user, schema_name]).encode()
        ).hexdigest()
        return self.cache_dir / f"{key}.json"

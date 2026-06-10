import itertools
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


class MissingGeminiKeysError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeminiKey:
    value: str
    index: int


class KeyRotator:
    def __init__(self, keys: list[str]):
        clean_keys = [k.strip() for k in keys if k.strip()]
        if not clean_keys:
            raise MissingGeminiKeysError(
                "No hay API keys de Gemini. Configura Gemini_key_1, Gemini_key_2, etc. en .env"
            )
        self._keys = [GeminiKey(value=k, index=i) for i, k in enumerate(clean_keys)]
        self._cycle = itertools.cycle(self._keys)

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    def next_key(self) -> GeminiKey:
        return next(self._cycle)


def indexed_gemini_keys() -> list[str]:
    indexed: list[tuple[int, str]] = []
    pattern = re.compile(r"^gemini_key_(\d+)$", re.IGNORECASE)
    for name, value in os.environ.items():
        match = pattern.match(name)
        if match and value.strip():
            indexed.append((int(match.group(1)), value.strip()))
    return [v for _, v in sorted(indexed, key=lambda x: x[0])]


def build_key_rotator() -> KeyRotator:
    return KeyRotator(indexed_gemini_keys())

# models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AudioNode:
    id: int
    name: str
    description: str
    media_class: str
    props: Dict[str, str]


@dataclass(frozen=True)
class InputChoice:
    kind: str   # "stream" | "source" | "sink"
    key: str    # "stream:<id>" | "source:<id>" | "sink:<id>"
    display: str


@dataclass(frozen=True)
class OutputChoice:
    key: str    # "sink:<id>"
    display: str

# models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class AudioNode:
    id: int
    name: str
    description: str
    media_class: str
    props: Dict[str, str]


@dataclass(frozen=True)
class InputChoice:
    # kind: "stream" | "source" | "sink"
    kind: str
    key: str  # "stream:<node_id>" | "source:<node_id>" | "sink:<node_id>"
    display: str


@dataclass(frozen=True)
class OutputChoice:
    key: str   # "sink:<node_id>"
    display: str

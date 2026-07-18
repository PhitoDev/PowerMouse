from dataclasses import dataclass


@dataclass(frozen=True)
class Microphone:
    id: str
    name: str

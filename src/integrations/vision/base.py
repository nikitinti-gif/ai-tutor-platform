from dataclasses import dataclass


@dataclass
class VisionResult:
    success: bool
    provider: str
    text: str
    confidence: float
    error: str | None = None
    raw_response: dict | None = None
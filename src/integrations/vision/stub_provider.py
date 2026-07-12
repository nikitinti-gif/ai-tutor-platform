from src.integrations.vision.base import VisionResult


class StubVisionProvider:
    def analyze(self, image_path: str) -> VisionResult:
        return VisionResult(
            success=True,
            provider="stub",
            text="есть ошибка при переносе слагаемого через знак равенства",
            confidence=0.75,
            error=None,
            raw_response={
                "image_path": image_path,
                "mode": "stub",
            },
        )
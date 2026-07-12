from paddleocr import PaddleOCR

from src.integrations.vision.base import VisionResult


class PaddleOCRProvider:
    def __init__(self):
        self.ocr = PaddleOCR(
            lang="ru",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def analyze(self, image_path: str) -> VisionResult:
        try:
            result = self.ocr.predict(image_path)

            lines = []

            if result and result[0]:
                for item in result[0]:
                    text = item[1][0]
                    lines.append(text)

            recognized_text = "\n".join(lines).strip()

            return VisionResult(
                success=bool(recognized_text),
                provider="paddleocr",
                text=recognized_text,
                confidence=0.75 if recognized_text else 0.0,
                error=None if recognized_text else "Text not recognized",
                raw_response={"raw": str(result)},
            )

        except Exception as error:
            return VisionResult(
                success=False,
                provider="paddleocr",
                text="",
                confidence=0.0,
                error=str(error),
                raw_response=None,
            )
        
import unittest
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter

from src.services.photo_quality_service import assess_homework_photo


def image_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


class PhotoQualityServiceTest(unittest.TestCase):
    def test_clear_page_is_accepted(self):
        image = Image.new("RGB", (1200, 1600), "white")
        drawing = ImageDraw.Draw(image)
        for y in range(100, 1500, 35):
            drawing.line((100, y, 1100, y), fill="black", width=3)

        result = assess_homework_photo(image_bytes(image))

        self.assertTrue(result.acceptable)
        self.assertEqual(result.issues, ())

    def test_blurred_page_requests_new_photo(self):
        image = Image.new("RGB", (1200, 1600), "white")
        drawing = ImageDraw.Draw(image)
        for y in range(100, 1500, 35):
            drawing.line((100, y, 1100, y), fill="black", width=3)
        image = image.filter(ImageFilter.GaussianBlur(12))

        result = assess_homework_photo(image_bytes(image))

        self.assertFalse(result.acceptable)
        self.assertTrue(
            any("размытым" in issue for issue in result.issues)
        )

    def test_small_image_is_rejected(self):
        image = Image.new("RGB", (500, 700), "gray")

        result = assess_homework_photo(image_bytes(image))

        self.assertFalse(result.acceptable)
        self.assertTrue(
            any("камеру ближе" in issue for issue in result.issues)
        )

    def test_invalid_file_is_rejected(self):
        with self.assertRaises(ValueError):
            assess_homework_photo(b"not-an-image")


if __name__ == "__main__":
    unittest.main()

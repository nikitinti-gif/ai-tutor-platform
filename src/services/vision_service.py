from src.integrations.vision.stub_provider import StubVisionProvider


class VisionService:
    def __init__(self):
        self.provider = StubVisionProvider()

    def analyze_homework_photo(self, image_path: str):
        return self.provider.analyze(image_path)
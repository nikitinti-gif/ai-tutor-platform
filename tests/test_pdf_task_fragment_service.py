from pathlib import Path

import fitz
from PIL import Image

from pdf_task_fragment_service import PdfTaskFragmentService


def _make_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((45, 90), "6. Previous task", fontsize=13)
    page.insert_text((45, 250), "7. Audio coding task", fontsize=13)
    page.draw_rect(fitz.Rect(70, 300, 400, 480), color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
    page.insert_text((90, 390), "DIAGRAM", fontsize=22)
    page.insert_text((45, 610), "8. Next task", fontsize=13)
    document.save(path)
    document.close()


def test_extracts_and_caches_task_fragment(tmp_path: Path):
    pdf = tmp_path / "variant.pdf"
    cache = tmp_path / "cache"
    _make_pdf(pdf)
    service = PdfTaskFragmentService(pdf_path=pdf, cache_dir=cache)

    first = service.get_fragment(7)
    second = service.get_fragment(7)

    assert first == second
    assert first.exists()
    with Image.open(first) as image:
        assert image.width > 300
        assert 180 < image.height < 600


def test_rejects_invalid_number(tmp_path: Path):
    service = PdfTaskFragmentService(
        pdf_path=tmp_path / "missing.pdf",
        cache_dir=tmp_path / "cache",
    )
    try:
        service.get_fragment(0)
    except ValueError as exc:
        assert "от 1 до 27" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")

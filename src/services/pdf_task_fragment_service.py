"""Automatic extraction of a single EGE task fragment from a PDF.

The service uses the PDF text layer to find the current task number and the
next task number, renders the area between them, and caches the resulting PNG.
No OCR, LLM, or Vision API is used.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


class TaskFragmentError(RuntimeError):
    """Raised when a task fragment cannot be prepared."""


@dataclass(frozen=True, slots=True)
class TaskAnchor:
    page_index: int
    y: float


class PdfTaskFragmentService:
    def __init__(
        self,
        *,
        pdf_path: str | Path,
        cache_dir: str | Path,
        pdf_url: str | None = None,
        zoom: float = 1.15,
        margin_top: float = 8.0,
        margin_bottom: float = 10.0,
    ) -> None:
        self.pdf_path = Path(pdf_path)
        self.cache_dir = Path(cache_dir)
        self.pdf_url = pdf_url
        self.zoom = zoom
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom

    def get_fragment(self, task_number: int) -> Path:
        if not 1 <= task_number <= 27:
            raise ValueError("Номер задания должен быть от 1 до 27.")

        self._ensure_pdf()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self.cache_dir / f"task_{task_number:02d}.png"
        meta_path = self.cache_dir / f"task_{task_number:02d}.sha256"
        fingerprint = self._pdf_fingerprint()

        if cache_path.exists() and meta_path.exists():
            if meta_path.read_text(encoding="utf-8").strip() == fingerprint:
                return cache_path

        temp_output = cache_path.with_suffix(".tmp.png")
        try:
            self._render_task(task_number, temp_output)
            temp_output.replace(cache_path)
            meta_path.write_text(fingerprint, encoding="utf-8")
        finally:
            temp_output.unlink(missing_ok=True)

        return cache_path

    def _ensure_pdf(self) -> None:
        if self.pdf_path.exists() and self.pdf_path.stat().st_size > 0:
            return
        if not self.pdf_url:
            raise TaskFragmentError(
                f"PDF не найден: {self.pdf_path}. URL для загрузки не задан."
            )

        self.pdf_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix="ege_variant_", suffix=".pdf", dir=self.pdf_path.parent
        )
        os.close(fd)
        temporary_path = Path(temporary_name)
        try:
            request = urllib.request.Request(
                self.pdf_url,
                headers={"User-Agent": "AI-Tutor-EGE/0.1"},
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                content_type = response.headers.get("Content-Type", "")
                with temporary_path.open("wb") as output:
                    shutil.copyfileobj(response, output)
            if temporary_path.stat().st_size < 10_000:
                raise TaskFragmentError("Загруженный PDF слишком мал или повреждён.")
            if "pdf" not in content_type.lower():
                # Some servers return application/octet-stream, so validate by opening.
                with fitz.open(temporary_path) as document:
                    if document.page_count < 2:
                        raise TaskFragmentError("Загруженный файл не похож на вариант КЕГЭ.")
            temporary_path.replace(self.pdf_path)
        except Exception as exc:
            raise TaskFragmentError(f"Не удалось загрузить PDF варианта: {exc}") from exc
        finally:
            temporary_path.unlink(missing_ok=True)

    def _pdf_fingerprint(self) -> str:
        stat = self.pdf_path.stat()
        raw = f"v3:{stat.st_size}:{stat.st_mtime_ns}:{self.zoom}".encode()
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _is_task_marker(text: str, number: int) -> bool:
        normalized = " ".join(text.replace("\xa0", " ").split())
        if not normalized:
            return False
        return bool(re.match(rf"^{number}(?:[.)]|\s|$)", normalized))

    def _find_anchor(self, document: fitz.Document, number: int) -> TaskAnchor:
        candidates: list[TaskAnchor] = []
        marker = str(number)

        for page_index in range(document.page_count):
            page = document[page_index]
            height = page.rect.height
            page_dict = page.get_text("dict")

            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    text = "".join(str(span.get("text", "")) for span in spans).strip()
                    if not re.match(rf"^{re.escape(marker)}(?:[.)]|\s)", text):
                        continue

                    x0, y0, x1, y1 = line.get("bbox", (0, 0, 0, 0))
                    if y0 < 35 or y0 > height - 45:
                        continue
                    # FIPI task markers are standalone and very close to the
                    # left page margin. This rejects row/column numbers in tables.
                    if x0 > 82:
                        continue
                    candidates.append(TaskAnchor(page_index, max(0.0, y0)))

        if not candidates:
            raise TaskFragmentError(f"Не удалось найти начало задания {number} в PDF.")

        return sorted(candidates, key=lambda item: (item.page_index, item.y))[0]

    @staticmethod
    def _content_rect(page: fitz.Page, top: float, hard_bottom: float) -> fitz.Rect:
        boxes: list[fitz.Rect] = []

        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = block
            text_norm = " ".join(str(text).split()).lower()
            if y1 <= top or y0 >= hard_bottom:
                continue
            if y0 > page.rect.height - 55:
                continue
            if "федеральная служба" in text_norm or "© 2026" in text_norm:
                continue
            boxes.append(fitz.Rect(x0, y0, x1, y1))

        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect and rect.y1 > top and rect.y0 < hard_bottom:
                boxes.append(fitz.Rect(rect))

        for image in page.get_images(full=True):
            try:
                for rect in page.get_image_rects(image[0]):
                    if rect.y1 > top and rect.y0 < hard_bottom:
                        boxes.append(fitz.Rect(rect))
            except Exception:
                continue

        if not boxes:
            return fitz.Rect(18.0, top, page.rect.width - 18.0, hard_bottom)

        left = max(0.0, min(box.x0 for box in boxes) - 14.0)
        right = min(page.rect.width, max(box.x1 for box in boxes) + 14.0)
        bottom = min(hard_bottom, max(box.y1 for box in boxes) + 14.0)
        return fitz.Rect(left, max(0.0, top - 5.0), right, bottom)

    def _render_task(self, task_number: int, output_path: Path) -> None:
        """Render a memory-bounded fragment.

        Render only the page containing the task start. This avoids keeping
        several large bitmaps in memory on 512 MB Render instances. If a task
        continues on the next page, the bot still provides the official PDF
        link as a fallback.
        """
        with fitz.open(self.pdf_path) as document:
            start = self._find_anchor(document, task_number)
            end = (
                self._find_anchor(document, task_number + 1)
                if task_number < 27
                else None
            )

            page = document[start.page_index]
            top = max(0.0, start.y - self.margin_top)
            if end and end.page_index == start.page_index:
                bottom = min(page.rect.height, end.y - self.margin_bottom)
            else:
                bottom = page.rect.height - 28.0

            if bottom - top < 40:
                raise TaskFragmentError(
                    f"Фрагмент задания {task_number} получился пустым."
                )

            clip = self._content_rect(page, top, bottom)
            if clip.height < 40 or clip.width < 80:
                raise TaskFragmentError(
                    f"Фрагмент задания {task_number} получился слишком мал."
                )

            # Limit output width to roughly 1100 px. This is readable in
            # Telegram and keeps peak memory safely below the Render limit.
            max_width_px = 1100.0
            safe_zoom = min(self.zoom, max_width_px / max(1.0, clip.width))
            safe_zoom = max(0.8, safe_zoom)

            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(safe_zoom, safe_zoom),
                clip=clip,
                alpha=False,
                colorspace=fitz.csRGB,
            )
            try:
                pixmap.save(output_path)
            finally:
                del pixmap

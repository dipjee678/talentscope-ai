"""Document extraction service for PDF, DOCX, and legacy DOC files with scanned-PDF OCR support."""
from __future__ import annotations

import base64
import io
import logging
import re
import shutil
from dataclasses import dataclass, field
from typing import List

import docx
import httpx
from pypdf import PdfReader

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CVExtractionOutput:
    text: str
    page_count: int
    ocr_status: str  # not_needed | completed_tesseract | completed_vision_llm | scanned_ocr_unavailable
    warnings: List[str] = field(default_factory=list)


async def _try_ocr_scanned_pdf(raw_bytes: bytes) -> tuple[str, str, List[str]]:
    """Attempt OCR on scanned PDFs using PyMuPDF + Tesseract if installed, or Vision LLM if configured."""
    warnings: List[str] = []

    # 1. Try local PyMuPDF + pytesseract if installed
    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image

        if shutil.which("tesseract"):
            pdf_doc = fitz.open(stream=raw_bytes, filetype="pdf")
            ocr_pages: List[str] = []
            for page_index in range(min(len(pdf_doc), 15)):
                pix = pdf_doc[page_index].get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_pages.append(pytesseract.image_to_string(img))
            joined = "\n\n".join(p.strip() for p in ocr_pages if p.strip())
            if joined:
                return joined, "completed_tesseract", warnings
    except Exception:
        pass

    # 2. Try Gemini Vision PDF OCR if GEMINI_API_KEY is configured
    settings = get_settings()
    if settings.GEMINI_API_KEY:
        try:
            b64_pdf = base64.b64encode(raw_bytes).decode("ascii")
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            )
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    url,
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "inlineData": {
                                            "mimeType": "application/pdf",
                                            "data": b64_pdf,
                                        }
                                    },
                                    {
                                        "text": (
                                            "Transcribe all visible text from this scanned CV verbatim. "
                                            "Do not invent, summarize, or add any text not visibly present."
                                        )
                                    },
                                ],
                            }
                        ],
                        "generationConfig": {"temperature": 0.0},
                    },
                )
                resp.raise_for_status()
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                if text and text.strip():
                    return text.strip(), "completed_vision_llm", warnings
        except Exception as exc:
            logger.warning("Vision OCR attempt failed: %s", type(exc).__name__)

    warnings.append(
        "This PDF appears to be a scanned image with minimal selectable text, and no local OCR engine "
        "(Tesseract) or Vision API key was available. Please review and complete extracted fields manually, "
        "or upload a text-based PDF/DOCX."
    )
    return "", "scanned_ocr_unavailable", warnings


async def extract_text_from_cv_bytes(filename: str, raw_bytes: bytes) -> CVExtractionOutput:
    lower = filename.lower()
    warnings: List[str] = []

    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw_bytes))
        page_count = len(reader.pages)
        pages_text: List[str] = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                pages_text.append("")
        combined = "\n\n".join(p.strip() for p in pages_text if p.strip())

        # Detect scanned image-only PDFs (very low character count relative to page count)
        alpha_chars = len(re.findall(r"[A-Za-z0-9]", combined))
        if alpha_chars < max(40, page_count * 25):
            ocr_text, ocr_status, ocr_warnings = await _try_ocr_scanned_pdf(raw_bytes)
            warnings.extend(ocr_warnings)
            if ocr_text.strip():
                combined = ocr_text
            return CVExtractionOutput(
                text=combined,
                page_count=page_count,
                ocr_status=ocr_status,
                warnings=warnings,
            )

        return CVExtractionOutput(
            text=combined,
            page_count=page_count,
            ocr_status="not_needed",
            warnings=warnings,
        )

    if lower.endswith(".docx"):
        doc = docx.Document(io.BytesIO(raw_bytes))
        blocks: List[str] = []
        for para in doc.paragraphs:
            if para.text and para.text.strip():
                blocks.append(para.text.strip())
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
                if cells:
                    blocks.append(" | ".join(dict.fromkeys(cells)))
        return CVExtractionOutput(
            text="\n".join(blocks),
            page_count=max(1, len(blocks) // 35 + 1),
            ocr_status="not_needed",
            warnings=warnings,
        )

    if lower.endswith(".doc"):
        # Extract readable ASCII/UTF-16 runs from legacy binary .doc or RTF without external COM automation
        ascii_runs = re.findall(rb"[\x20-\x7e\r\n\t]{5,}", raw_bytes)
        utf16_runs = re.findall(rb"(?:[\x20-\x7e]\x00){5,}", raw_bytes)
        parts = [r.decode("latin-1", errors="ignore") for r in ascii_runs]
        parts.extend(r.decode("utf-16le", errors="ignore") for r in utf16_runs)
        # Filter out OLE/Word internal metadata tokens
        junk_tokens = {"Word.Document", "MSWordDoc", "Normal.dotm", "Root Entry", "CompObj", "SummaryInformation"}
        clean_lines = []
        for chunk in parts:
            line = chunk.strip()
            if line and not any(tok in line for tok in junk_tokens):
                clean_lines.append(line)
        warnings.append(
            "Legacy .doc format was parsed via binary text extraction. For highest structural accuracy, "
            "uploading PDF or DOCX is recommended."
        )
        return CVExtractionOutput(
            text="\n".join(clean_lines),
            page_count=1,
            ocr_status="not_needed",
            warnings=warnings,
        )

    raise ValueError("Unsupported CV file format.")

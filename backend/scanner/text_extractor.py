"""
DataGhost – text extraction from files.
Supports plain text, PDF, DOCX, and falls back to UTF-8 decode for unknown types.
"""
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum characters returned from any single file.
MAX_TEXT_LENGTH = 50_000

# Extensions treated as plain text.
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".xml",
    ".yaml", ".yml", ".env", ".cfg", ".ini", ".log", ".csv",
    ".html", ".htm", ".sh", ".bat", ".ps1", ".rb", ".go",
    ".java", ".c", ".cpp", ".h",
}


def _ext(filename: str) -> str:
    """Return the lowercase file extension including the dot, e.g. '.pdf'."""
    dot = filename.rfind(".")
    if dot == -1:
        return ""
    return filename[dot:].lower()


def _decode_bytes(data: bytes) -> str:
    """Try UTF-8 first, then let chardet detect the encoding."""
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        pass
    try:
        import chardet
        detected = chardet.detect(data)
        enc = detected.get("encoding") or "utf-8"
        return data.decode(enc, errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")


def _extract_pdf(content: bytes) -> str:
    """Extract text from a PDF using PyPDF2."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    parts.append(text)
            except Exception:
                pass
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def _extract_docx(content: bytes) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        # Also pull table cells.
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        paragraphs.append(cell.text)
        return "\n".join(paragraphs)
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        return ""


def extract_text(file_content: bytes, filename: str) -> str:
    """
    Extract plain text from file bytes.

    Parameters
    ----------
    file_content : bytes
        Raw file bytes.
    filename : str
        Original filename (used to determine handler by extension).

    Returns
    -------
    str
        Extracted text, at most MAX_TEXT_LENGTH characters.
    """
    ext = _ext(filename)

    if ext in _TEXT_EXTENSIONS:
        text = _decode_bytes(file_content)
    elif ext == ".pdf":
        text = _extract_pdf(file_content)
    elif ext == ".docx":
        text = _extract_docx(file_content)
    else:
        # Best-effort UTF-8 decode for any other extension.
        try:
            text = _decode_bytes(file_content)
        except Exception:
            logger.warning("Could not extract text from %s", filename)
            text = ""

    return text[:MAX_TEXT_LENGTH]

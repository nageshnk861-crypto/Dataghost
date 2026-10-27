"""
DataGhost – text extraction from files.
Supports plain text, PDF, DOCX, and falls back to UTF-8 decode for unknown types.
"""
import io
import logging

logger = logging.getLogger(__name__)

# Maximum characters returned from any single file (1 MB text window).
MAX_TEXT_LENGTH = 1_000_000

# Extensions treated as plain text.
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".xml",
    ".yaml", ".yml", ".env", ".cfg", ".ini", ".log", ".csv",
    ".html", ".htm", ".sh", ".bash", ".bat", ".ps1", ".rb", ".go",
    ".java", ".c", ".cpp", ".h", ".sql", ".conf", ".toml",
    ".properties", ".proto", ".key", ".pem", ".crt",
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


def _extract_xlsx(content: bytes) -> str:
    """Extract text from an XLSX/XLS file using zipfile XML inspection."""
    import zipfile
    import xml.etree.ElementTree as ET
    parts = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for name in z.namelist():
                if name.startswith("xl/sharedStrings") or name.startswith("xl/worksheets/"):
                    try:
                        tree = ET.fromstring(z.read(name))
                        parts.extend(tree.itertext())
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("XLSX extraction failed: %s", exc)
    return " ".join(parts)


def _extract_pptx(content: bytes) -> str:
    """Extract text from a PPTX file using slide XML text extraction."""
    import zipfile
    import xml.etree.ElementTree as ET
    parts = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for name in z.namelist():
                if name.startswith("ppt/slides/slide") or name.startswith("ppt/notesSlides/"):
                    try:
                        tree = ET.fromstring(z.read(name))
                        parts.extend(tree.itertext())
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("PPTX extraction failed: %s", exc)
    return " ".join(parts)


def _extract_zip(content: bytes) -> str:
    """Extract and aggregate text from files inside a ZIP archive."""
    import zipfile
    parts = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for item in z.infolist():
                if item.is_dir() or item.file_size > 2 * 1024 * 1024:
                    continue
                inner_ext = _ext(item.filename)
                if inner_ext in _TEXT_EXTENSIONS or inner_ext in (".pdf", ".docx", ".xlsx", ".pptx"):
                    inner_bytes = z.read(item)
                    parts.append(f"--- File: {item.filename} ---")
                    parts.append(extract_text(inner_bytes, item.filename))
    except Exception as exc:
        logger.warning("ZIP extraction failed: %s", exc)
    return "\n".join(parts)


def _extract_tar_gz(content: bytes, filename: str) -> str:
    """Extract and aggregate text from files inside a TAR or GZ archive."""
    import tarfile
    import gzip
    parts = []
    try:
        with tarfile.open(fileobj=io.BytesIO(content)) as tar:
            for member in tar.getmembers():
                if not member.isfile() or member.size > 2 * 1024 * 1024:
                    continue
                inner_ext = _ext(member.name)
                if inner_ext in _TEXT_EXTENSIONS or inner_ext in (".pdf", ".docx", ".xlsx", ".pptx"):
                    f = tar.extractfile(member)
                    if f:
                        inner_bytes = f.read()
                        parts.append(f"--- File: {member.name} ---")
                        parts.append(extract_text(inner_bytes, member.name))
        if parts:
            return "\n".join(parts)
    except Exception:
        pass

    # Fallback for standalone .gz files
    try:
        decompressed = gzip.decompress(content)
        inner_name = filename[:-3] if filename.lower().endswith(".gz") else filename
        return extract_text(decompressed, inner_name)
    except Exception as exc:
        logger.warning("TAR/GZ extraction failed: %s", exc)
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
    elif ext in (".xlsx", ".xls"):
        text = _extract_xlsx(file_content)
    elif ext in (".pptx", ".ppt"):
        text = _extract_pptx(file_content)
    elif ext == ".zip":
        text = _extract_zip(file_content)
    elif ext in (".tar", ".gz", ".tgz"):
        text = _extract_tar_gz(file_content, filename)
    else:
        # Best-effort UTF-8 decode for any other extension.
        try:
            text = _decode_bytes(file_content)
        except Exception:
            logger.warning("Could not extract text from %s", filename)
            text = ""

    return text[:MAX_TEXT_LENGTH]

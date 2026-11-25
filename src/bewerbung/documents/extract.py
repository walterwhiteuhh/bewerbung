"""Dateityp über Magic Bytes bestimmen und Text aus PDF/Word/Text auslesen.

Der Dateityp kommt bewusst nicht aus Dateiendung oder ``Content-Type`` des Browsers,
sondern aus dem Inhalt: so landet nichts Unerwartetes in der Ablage.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "x1"
MAX_TEXT_CHARS = 200_000
# Schutz vor Zip-Bomben: entpacktes document.xml darf nicht beliebig groß sein.
_MAX_DOCX_XML_BYTES = 30 * 1024 * 1024
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True, slots=True)
class FileType:
    ext: str
    mime: str
    label: str


PDF = FileType(".pdf", "application/pdf", "PDF")
DOCX = FileType(
    ".docx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "Word",
)
PNG = FileType(".png", "image/png", "Bild")
JPEG = FileType(".jpg", "image/jpeg", "Bild")
TEXT = FileType(".txt", "text/plain; charset=utf-8", "Text")


class UnsupportedFileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Extraction:
    text: str | None
    page_count: int | None
    warning: str | None = None


def detect_type(data: bytes, filename: str) -> FileType:
    if data.startswith(b"%PDF-"):
        return PDF
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if "word/document.xml" in zf.namelist():
                    return DOCX
        except zipfile.BadZipFile:
            pass
        raise UnsupportedFileError("Nur Word-Dateien (.docx) werden als Office-Format unterstützt")
    if filename.lower().endswith((".txt", ".md")):
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedFileError("Textdatei ist nicht UTF-8-kodiert") from exc
        return TEXT
    if filename.lower().endswith(".doc"):
        raise UnsupportedFileError("Altes Word-Format (.doc): bitte als .docx oder PDF speichern")
    raise UnsupportedFileError("Erlaubt sind PDF, Word (.docx), Text, PNG und JPG")


def _clean(text: str) -> str | None:
    text = text.replace("\x00", "")
    text = re.sub("[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()
    return text[:MAX_TEXT_CHARS] or None


def _pdf(data: bytes) -> Extraction:
    from pypdf import PdfReader  # noqa: PLC0415 - nur bei PDFs laden

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return Extraction(None, None, "PDF ist passwortgeschützt, Text nicht lesbar")
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = _clean("\n\n".join(pages))
    warning = None if text else "Kein Text gefunden (gescanntes PDF?)"
    return Extraction(text, len(pages), warning)


def _docx(data: bytes) -> Extraction:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        info = zf.getinfo("word/document.xml")
        if info.file_size > _MAX_DOCX_XML_BYTES:
            return Extraction(None, None, "Word-Datei zu groß zum Auslesen")
        root = ET.fromstring(zf.read(info))
    paragraphs: list[str] = []
    for p in root.iter(f"{_W}p"):
        parts: list[str] = []
        for node in p.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    return Extraction(_clean("\n".join(paragraphs)), None)


def extract_text(data: bytes, ftype: FileType) -> Extraction:
    """Fehler beim Auslesen sind kein Upload-Fehler: Datei bleibt, Text fehlt dann eben."""
    try:
        if ftype is PDF:
            return _pdf(data)
        if ftype is DOCX:
            return _docx(data)
        if ftype is TEXT:
            return Extraction(_clean(data.decode("utf-8-sig")), None)
    except Exception as exc:
        logger.warning("Text konnte nicht ausgelesen werden (%s): %s", ftype.label, exc)
        return Extraction(None, None, "Text konnte nicht ausgelesen werden")
    return Extraction(None, None)

"""Unterlagen hochladen, auslesen, verwalten und Bewerbungen zuordnen."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from bewerbung.db.models import Document, PostingDocument
from bewerbung.db.types import utcnow
from bewerbung.documents.extract import (
    EXTRACTOR_VERSION,
    UnsupportedFileError,
    detect_type,
    extract_text,
)
from bewerbung.domain.errors import DomainError, DuplicateDocumentError, NotFoundError
from bewerbung.domain.schemas import DocumentKind, DocumentRead, DocumentUpdate
from bewerbung.services.letters import get_profile
from bewerbung.services.postings import get_posting

logger = logging.getLogger(__name__)

_PREVIEW_CHARS = 280
_CV_HINT = re.compile(r"lebenslauf|\bcv\b|curriculum|resume|résumé", re.IGNORECASE)


class DocumentStore:
    """Dateiablage, inhaltsadressiert: ``<sha256><ext>``. Gleiche Datei = gleicher Pfad."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, storage_key: str) -> Path:
        # storage_key stammt nur aus der DB und besteht aus Hex + Endung: kein Pfad-Trick möglich.
        if not re.fullmatch(r"[0-9a-f]{64}\.[a-z]{3,4}", storage_key):
            raise DomainError("Ungültiger Speicherschlüssel")
        return self.root / storage_key

    def save(self, storage_key: str, data: bytes) -> None:
        target = self.path(storage_key)
        if target.exists():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        # Erst in eine Temp-Datei schreiben, dann atomar umbenennen: keine halben Dateien.
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            Path(tmp).replace(target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def guess_kind(filename: str) -> DocumentKind:
    name = filename.lower()
    if _CV_HINT.search(name):
        return "lebenslauf"
    if "zeugnis" in name or "referenz" in name:
        return "zeugnis"
    if "zertifikat" in name or "certificate" in name or "nachweis" in name:
        return "zertifikat"
    if "anschreiben" in name or "cover" in name:
        return "anschreiben"
    return "sonstiges"


def _title_from(filename: str) -> str:
    stem = Path(filename).stem.replace("_", " ").strip()
    return (stem or "Dokument")[:255]


def _safe_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^\w.\- ()äöüÄÖÜß]", "_", name).strip(" .")
    return (name or "dokument")[:255]


def upload(
    session: Session,
    store: DocumentStore,
    *,
    data: bytes,
    filename: str,
    kind: DocumentKind | None = None,
    title: str | None = None,
) -> Document:
    if not data:
        raise DomainError("Die Datei ist leer")
    filename = _safe_filename(filename)
    try:
        ftype = detect_type(data, filename)
    except UnsupportedFileError as exc:
        raise DomainError(str(exc)) from exc

    sha = hashlib.sha256(data).hexdigest()
    existing = session.scalar(
        select(Document.id).where(Document.sha256 == sha, Document.archived_at.is_(None))
    )
    if existing is not None:
        raise DuplicateDocumentError(existing)

    storage_key = f"{sha}{ftype.ext}"
    store.save(storage_key, data)
    extraction = extract_text(data, ftype)
    kind = kind or guess_kind(filename)

    doc = Document(
        kind=kind,
        title=(title or _title_from(filename))[:255],
        filename=filename,
        content_type=ftype.mime,
        size_bytes=len(data),
        sha256=sha,
        storage_key=storage_key,
        page_count=extraction.page_count,
        text_content=extraction.text,
        extractor_version=EXTRACTOR_VERSION,
        # Der erste Lebenslauf wird automatisch der Haupt-Lebenslauf.
        is_primary=kind == "lebenslauf" and primary_cv(session) is None,
    )
    session.add(doc)
    session.flush()
    logger.info(
        "Dokument %s hochgeladen (%s, %s Bytes, Text: %s)",
        doc.id,
        ftype.label,
        len(data),
        "ja" if extraction.text else extraction.warning or "nein",
    )
    return doc


def list_documents(session: Session, *, include_archived: bool = False) -> list[Document]:
    stmt = select(Document).order_by(Document.is_primary.desc(), Document.created_at.desc())
    if not include_archived:
        stmt = stmt.where(Document.archived_at.is_(None))
    return list(session.scalars(stmt))


def get_document(session: Session, document_id: int) -> Document:
    doc = session.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Dokument", document_id)
    return doc


def primary_cv(session: Session) -> Document | None:
    return session.scalar(
        select(Document)
        .where(
            Document.kind == "lebenslauf",
            Document.is_primary.is_(True),
            Document.archived_at.is_(None),
        )
        .limit(1)
    )


def _clear_primary(session: Session, keep_id: int) -> None:
    session.execute(
        update(Document)
        .where(Document.is_primary.is_(True), Document.id != keep_id)
        .values(is_primary=False)
    )


def update_document(session: Session, document_id: int, data: DocumentUpdate) -> Document:
    doc = get_document(session, document_id)
    if data.kind is not None:
        doc.kind = data.kind
        if doc.kind != "lebenslauf":
            doc.is_primary = False
    if data.title is not None:
        doc.title = data.title
    if data.is_primary is not None:
        if data.is_primary and doc.kind != "lebenslauf":
            raise DomainError("Nur ein Lebenslauf kann Haupt-Lebenslauf sein")
        if data.is_primary:
            _clear_primary(session, doc.id)
        doc.is_primary = data.is_primary
    session.flush()
    return doc


def archive_document(session: Session, document_id: int) -> Document:
    """Soft-Delete. Die Datei bleibt liegen, weil frühere Bewerbungen auf sie verweisen."""
    doc = get_document(session, document_id)
    doc.archived_at = doc.archived_at or utcnow()
    doc.is_primary = False
    session.flush()
    return doc


def use_as_cv_text(session: Session, document_id: int) -> Document:
    """Ausgelesenen Text ins Profil übernehmen (Feld "Lebenslauf")."""
    doc = get_document(session, document_id)
    if not doc.text_content:
        raise DomainError("Aus dieser Datei konnte kein Text gelesen werden")
    profile = get_profile(session)
    profile.cv_text = doc.text_content[:50_000]
    session.flush()
    return doc


# --- Zuordnung zu Stellen -------------------------------------------------------


def posting_documents(session: Session, posting_id: int) -> list[Document]:
    get_posting(session, posting_id)
    stmt = (
        select(Document)
        .join(PostingDocument, PostingDocument.document_id == Document.id)
        .where(PostingDocument.posting_id == posting_id, PostingDocument.detached_at.is_(None))
        .order_by(PostingDocument.attached_at)
    )
    return list(session.scalars(stmt))


def set_posting_documents(
    session: Session, posting_id: int, document_ids: list[int]
) -> list[Document]:
    get_posting(session, posting_id)
    wanted = list(dict.fromkeys(document_ids))
    for doc_id in wanted:
        doc = get_document(session, doc_id)
        if doc.archived_at is not None:
            raise DomainError(f"Dokument {doc_id} ist archiviert")
    active = {
        link.document_id: link
        for link in session.scalars(
            select(PostingDocument).where(
                PostingDocument.posting_id == posting_id, PostingDocument.detached_at.is_(None)
            )
        )
    }
    now = utcnow()
    for doc_id, link in active.items():
        if doc_id not in wanted:
            link.detached_at = now
    for doc_id in wanted:
        if doc_id not in active:
            session.add(PostingDocument(posting_id=posting_id, document_id=doc_id, attached_at=now))
    session.flush()
    return posting_documents(session, posting_id)


def to_read(doc: Document) -> DocumentRead:
    text = doc.text_content
    return DocumentRead(
        id=doc.id,
        kind=doc.kind,
        title=doc.title,
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        page_count=doc.page_count,
        has_text=bool(text),
        text_preview=(text[:_PREVIEW_CHARS] + ("…" if len(text) > _PREVIEW_CHARS else ""))
        if text
        else None,
        is_primary=doc.is_primary,
        created_at=doc.created_at,
        archived_at=doc.archived_at,
    )

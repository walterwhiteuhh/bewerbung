"""Unterlagen hochladen, auslesen und Bewerbungen zuordnen."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from bewerbung.api.deps import DocumentStoreDep, SessionDep
from bewerbung.domain.errors import DomainError
from bewerbung.domain.schemas import (
    DocumentKind,
    DocumentRead,
    DocumentText,
    DocumentUpdate,
    PostingDocumentsUpdate,
    PrimaryCvPeriodRead,
    ProfileRead,
)
from bewerbung.services import documents, letters

router = APIRouter()


_UPLOAD_CHUNK = 1024 * 1024


@router.get("/documents", response_model=list[DocumentRead], tags=["documents"])
def list_documents(session: SessionDep, include_archived: bool = False) -> list[DocumentRead]:
    docs = documents.list_documents(session, include_archived=include_archived)
    return [documents.to_read(d) for d in docs]


@router.post(
    "/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def upload_document(
    *,
    request: Request,
    session: SessionDep,
    store: DocumentStoreDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[DocumentKind | None, Form()] = None,
    title: Annotated[str | None, Form(max_length=255)] = None,
) -> DocumentRead:
    """PDF, Word (.docx), Text, PNG oder JPG; Text wird ausgelesen. 409 bei Dublette."""
    limit: int = request.app.state.max_upload_bytes
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(_UPLOAD_CHUNK):
        size += len(chunk)
        if size > limit:
            raise DomainError(f"Datei ist größer als {limit // (1024 * 1024)} MB")
        chunks.append(chunk)
    # Hashen, Textauslese (PDF/Word) und Schreiben sind blockierend: raus aus dem Event-Loop.
    doc = await run_in_threadpool(
        documents.upload,
        session,
        store,
        data=b"".join(chunks),
        filename=file.filename or "dokument",
        kind=kind,
        title=title or None,
    )
    return documents.to_read(doc)


@router.get(
    "/documents/primary-history", response_model=list[PrimaryCvPeriodRead], tags=["documents"]
)
def primary_cv_history(session: SessionDep) -> list[PrimaryCvPeriodRead]:
    """Wann welche Unterlage Haupt-Lebenslauf war und wie viele Bewerbungen darin rausgingen."""
    return documents.primary_history(session)


@router.get("/documents/{document_id}/file", tags=["documents"])
def download_document(
    session: SessionDep, store: DocumentStoreDep, document_id: int, download: bool = False
) -> FileResponse:
    doc = documents.get_document(session, document_id)
    path = store.path(doc.storage_key)
    if not path.is_file():
        raise DomainError("Datei fehlt in der Ablage")
    inline = not download and doc.content_type.startswith(("application/pdf", "image/"))
    return FileResponse(
        path,
        media_type=doc.content_type,
        filename=doc.filename,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/documents/{document_id}/text", response_model=DocumentText, tags=["documents"])
def document_text(session: SessionDep, document_id: int) -> DocumentText:
    doc = documents.get_document(session, document_id)
    return DocumentText(id=doc.id, text=doc.text_content)


@router.patch("/documents/{document_id}", response_model=DocumentRead, tags=["documents"])
def patch_document(session: SessionDep, document_id: int, data: DocumentUpdate) -> DocumentRead:
    return documents.to_read(documents.update_document(session, document_id, data))


@router.post("/documents/{document_id}/archive", response_model=DocumentRead, tags=["documents"])
def archive_document(session: SessionDep, document_id: int) -> DocumentRead:
    return documents.to_read(documents.archive_document(session, document_id))


@router.post("/documents/{document_id}/use-as-cv", response_model=ProfileRead, tags=["documents"])
def use_document_as_cv(session: SessionDep, document_id: int) -> ProfileRead:
    """Ausgelesenen Text in das Profilfeld "Lebenslauf" übernehmen."""
    documents.use_as_cv_text(session, document_id)
    return ProfileRead.model_validate(letters.get_profile(session))


@router.get(
    "/postings/{posting_id}/documents", response_model=list[DocumentRead], tags=["documents"]
)
def get_posting_documents(session: SessionDep, posting_id: int) -> list[DocumentRead]:
    return [documents.to_read(d) for d in documents.posting_documents(session, posting_id)]


@router.put(
    "/postings/{posting_id}/documents", response_model=list[DocumentRead], tags=["documents"]
)
def put_posting_documents(
    session: SessionDep, posting_id: int, data: PostingDocumentsUpdate
) -> list[DocumentRead]:
    """Unterlagen dieser Bewerbung setzen; Entfernte bleiben mit ``ended_at`` erhalten."""
    docs = documents.set_posting_documents(session, posting_id, data.document_ids)
    return [documents.to_read(d) for d in docs]

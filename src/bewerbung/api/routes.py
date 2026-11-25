"""REST-Endpunkte unter ``/api``. Dünne Schicht: Validierung -> Service -> Schema."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from bewerbung.api.deps import (
    AaLogosDep,
    DocumentStoreDep,
    FetcherDep,
    LetterGeneratorsDep,
    LogoStoreDep,
    ProvidersDep,
    RegistryDep,
    SessionDep,
    SiteLogosDep,
)
from bewerbung.domain.errors import DomainError
from bewerbung.domain.schemas import (
    ApplicationRead,
    ApplicationUpdate,
    CompanyRead,
    CompanyUpdate,
    CoverLetterRead,
    CoverLetterRequest,
    CoverLetterUpdate,
    DocumentKind,
    DocumentRead,
    DocumentText,
    DocumentUpdate,
    GeneratorInfo,
    ImportPreview,
    ImportRequest,
    LetterContextPreview,
    ListingRead,
    NoteCreate,
    NoteRead,
    PostingCreate,
    PostingDetail,
    PostingDocumentsUpdate,
    PostingFilter,
    PostingListItem,
    PostingPage,
    PostingUpdate,
    ProfileRead,
    ProfileUpdate,
    ProviderInfo,
    SaveListing,
    SearchProfileCreate,
    SearchProfileRead,
    SearchRequest,
    SearchRunRead,
    SearchRunSummary,
    SourceDetection,
    Stats,
    StatusChange,
    TagCount,
)
from bewerbung.services import (
    applications,
    companies,
    documents,
    importer,
    letters,
    postings,
    search,
    stats,
    tags,
)
from bewerbung.sources.site_logo import MEDIA_TYPES

router = APIRouter(prefix="/api")


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/logos/arbeitsagentur/{logo_hash}", tags=["search"], include_in_schema=False)
async def arbeitsagentur_logo(cache: AaLogosDep, logo_hash: str) -> FileResponse:
    """Arbeitgeberlogo der Arbeitsagentur (einmal geladen, dann lokal aus dem Cache)."""
    logo = await cache.get(logo_hash)
    if logo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Logo")
    return FileResponse(
        logo.path,
        media_type=logo.media_type,
        headers={"Cache-Control": "public, max-age=604800", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/logos/files/{name}", tags=["companies"], include_in_schema=False)
def logo_file(store: LogoStoreDep, name: str) -> FileResponse:
    """Lokal abgelegtes Firmenlogo (von der Firmen-Website geladen)."""
    path = store.path(name)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Logo")
    ext = name.rsplit(".", 1)[-1]
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[ext],
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",  # Name = Inhalts-Hash
            "X-Content-Type-Options": "nosniff",
            # SVG darf beim direkten Öffnen keine Skripte ausführen.
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        },
    )


@router.get("/companies", response_model=list[CompanyRead], tags=["companies"])
def list_companies(session: SessionDep) -> list[CompanyRead]:
    return [companies.to_read(c, n) for c, n in companies.list_companies(session)]


@router.get("/companies/{company_id}", response_model=CompanyRead, tags=["companies"])
def get_company(session: SessionDep, company_id: int) -> CompanyRead:
    return companies.to_read(companies.get_company(session, company_id))


@router.patch("/companies/{company_id}", response_model=CompanyRead, tags=["companies"])
def update_company(session: SessionDep, company_id: int, data: CompanyUpdate) -> CompanyRead:
    return companies.to_read(companies.update_company(session, company_id, data))


@router.post("/companies/{company_id}/logo", response_model=CompanyRead, tags=["companies"])
async def fetch_company_logo(
    session: SessionDep, store: LogoStoreDep, fetcher: SiteLogosDep, company_id: int
) -> CompanyRead:
    """Logo von der hinterlegten Firmen-Website laden (ersetzt das bisherige Logo)."""
    company = await companies.fetch_logo_from_website(session, store, fetcher, company_id)
    return companies.to_read(company)


@router.get("/sources/detect", response_model=SourceDetection, tags=["sources"])
def detect_source(
    session: SessionDep, registry: RegistryDep, url: Annotated[str, Query(min_length=4)]
) -> SourceDetection:
    """Quelle, externe ID und mögliche Dublette zu einer eingefügten URL bestimmen."""
    return postings.detect_source(session, registry, url)


@router.post("/sources/import", response_model=ImportPreview, tags=["sources"])
async def import_preview(
    session: SessionDep, registry: RegistryDep, fetcher: FetcherDep, data: ImportRequest
) -> ImportPreview:
    """Anzeige laden und Felder vorschlagen. Speichert nichts; 502, wenn die Seite nicht lädt."""
    return await importer.preview_import(session, registry, fetcher, data.url)


# --- Stellen -----------------------------------------------------------------


@router.get("/postings", response_model=PostingPage, tags=["postings"])
def list_postings(session: SessionDep, flt: Annotated[PostingFilter, Query()]) -> PostingPage:
    """Filter: ``q`` (Freitext), ``status``/``source``/``tag`` (mehrfach), Sortierung, Paginierung.

    Mehrere ``tag``-Werte sind UND-verknüpft: nur Stellen, die alle Hashtags tragen.
    """
    items, total = postings.list_postings(session, flt)
    return PostingPage(
        items=[PostingListItem.model_validate(p) for p in items],
        total=total,
        limit=flt.limit,
        offset=flt.offset,
    )


@router.post(
    "/postings",
    response_model=PostingDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["postings"],
)
def create_posting(
    session: SessionDep, registry: RegistryDep, data: PostingCreate
) -> PostingDetail:
    posting = postings.create_posting(session, registry, data)
    return PostingDetail.model_validate(postings.get_posting(session, posting.id))


@router.get("/postings/{posting_id}", response_model=PostingDetail, tags=["postings"])
def get_posting(session: SessionDep, posting_id: int) -> PostingDetail:
    return PostingDetail.model_validate(postings.get_posting(session, posting_id))


@router.patch("/postings/{posting_id}", response_model=PostingDetail, tags=["postings"])
def update_posting(
    session: SessionDep, registry: RegistryDep, posting_id: int, data: PostingUpdate
) -> PostingDetail:
    postings.update_posting(session, registry, posting_id, data)
    return PostingDetail.model_validate(postings.get_posting(session, posting_id))


@router.post("/postings/{posting_id}/archive", response_model=PostingDetail, tags=["postings"])
def archive_posting(session: SessionDep, posting_id: int) -> PostingDetail:
    """Soft-Delete: die Stelle verschwindet aus Listen, die Historie bleibt erhalten."""
    return PostingDetail.model_validate(postings.set_archived(session, posting_id, archived=True))


@router.post("/postings/{posting_id}/restore", response_model=PostingDetail, tags=["postings"])
def restore_posting(session: SessionDep, posting_id: int) -> PostingDetail:
    return PostingDetail.model_validate(postings.set_archived(session, posting_id, archived=False))


# --- Bewerbungen -------------------------------------------------------------


@router.get("/applications/{application_id}", response_model=ApplicationRead, tags=["applications"])
def get_application(session: SessionDep, application_id: int) -> ApplicationRead:
    return ApplicationRead.model_validate(applications.get_application(session, application_id))


@router.patch(
    "/applications/{application_id}", response_model=ApplicationRead, tags=["applications"]
)
def update_application(
    session: SessionDep, application_id: int, data: ApplicationUpdate
) -> ApplicationRead:
    return ApplicationRead.model_validate(
        applications.update_application(session, application_id, data)
    )


@router.post(
    "/applications/{application_id}/status",
    response_model=ApplicationRead,
    tags=["applications"],
)
def change_status(session: SessionDep, application_id: int, data: StatusChange) -> ApplicationRead:
    return ApplicationRead.model_validate(applications.change_status(session, application_id, data))


@router.post(
    "/applications/{application_id}/notes",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    tags=["applications"],
)
def add_note(session: SessionDep, application_id: int, data: NoteCreate) -> NoteRead:
    return NoteRead.model_validate(applications.add_note(session, application_id, data))


# --- Live-Suche ----------------------------------------------------------------


@router.get("/search/providers", response_model=list[ProviderInfo], tags=["search"])
def search_providers(providers: ProvidersDep) -> list[ProviderInfo]:
    return search.provider_infos(providers)


@router.post("/search", response_model=SearchRunRead, tags=["search"])
async def run_search(
    session: SessionDep, registry: RegistryDep, providers: ProvidersDep, data: SearchRequest
) -> SearchRunRead:
    """Gewählte Portale parallel durchsuchen; Fehler einzelner Portale stehen in ``errors``."""
    run = await search.run_search(session, registry, providers, data)
    return SearchRunRead.model_validate(run)


@router.get("/search/runs", response_model=list[SearchRunSummary], tags=["search"])
def list_runs(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[SearchRunSummary]:
    return [SearchRunSummary.model_validate(r) for r in search.list_runs(session, limit)]


@router.delete("/search/runs", tags=["search"])
def clear_runs(session: SessionDep) -> dict[str, int]:
    """Verlauf leeren: Läufe werden ausgeblendet, nicht gelöscht (Auswertung bleibt möglich)."""
    return {"hidden": search.hide_all_runs(session)}


@router.delete("/search/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["search"])
def delete_run(session: SessionDep, run_id: int) -> None:
    search.hide_run(session, run_id)


@router.get("/search/runs/{run_id}", response_model=SearchRunRead, tags=["search"])
def get_run(session: SessionDep, run_id: int) -> SearchRunRead:
    return SearchRunRead.model_validate(search.get_run(session, run_id))


@router.get("/search/profiles", response_model=list[SearchProfileRead], tags=["search"])
def list_profiles(session: SessionDep) -> list[SearchProfileRead]:
    return [SearchProfileRead.model_validate(p) for p in search.list_profiles(session)]


@router.post(
    "/search/profiles",
    response_model=SearchProfileRead,
    status_code=status.HTTP_201_CREATED,
    tags=["search"],
)
def create_profile(session: SessionDep, data: SearchProfileCreate) -> SearchProfileRead:
    return SearchProfileRead.model_validate(search.create_profile(session, data))


@router.put("/search/profiles/{profile_id}", response_model=SearchProfileRead, tags=["search"])
def put_search_profile(
    session: SessionDep, profile_id: int, data: SearchProfileCreate
) -> SearchProfileRead:
    return SearchProfileRead.model_validate(search.update_profile(session, profile_id, data))


@router.delete(
    "/search/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["search"]
)
def delete_profile(session: SessionDep, profile_id: int) -> None:
    search.archive_profile(session, profile_id)


@router.get("/listings/{listing_id}", response_model=ListingRead, tags=["search"])
def get_listing(session: SessionDep, listing_id: int) -> ListingRead:
    return ListingRead.model_validate(search.get_listing(session, listing_id))


@router.post("/listings/{listing_id}/save", response_model=PostingDetail, tags=["search"])
def save_listing(
    session: SessionDep, registry: RegistryDep, listing_id: int, data: SaveListing
) -> PostingDetail:
    """Treffer merken: legt Stelle und Bewerbung an (mehrfacher Aufruf ist unschädlich)."""
    return PostingDetail.model_validate(search.save_listing(session, registry, listing_id, data))


# --- Statistik ---------------------------------------------------------------


@router.get("/tags", response_model=list[TagCount], tags=["postings"])
def list_tags(session: SessionDep) -> list[TagCount]:
    """Alle Hashtags mit Anzahl der (nicht archivierten) Stellen, häufigste zuerst."""
    return tags.list_tags(session)


@router.get("/stats", response_model=Stats, tags=["stats"])
def get_stats(session: SessionDep) -> Stats:
    return stats.compute_stats(session)


# --- Profil & Anschreiben ----------------------------------------------------


@router.get("/profile", response_model=ProfileRead, tags=["letters"])
def get_profile(session: SessionDep) -> ProfileRead:
    return ProfileRead.model_validate(letters.get_profile(session))


@router.put("/profile", response_model=ProfileRead, tags=["letters"])
def put_profile(session: SessionDep, data: ProfileUpdate) -> ProfileRead:
    return ProfileRead.model_validate(letters.update_profile(session, data))


@router.get("/letters/generators", response_model=list[GeneratorInfo], tags=["letters"])
def list_generators(generators: LetterGeneratorsDep) -> list[GeneratorInfo]:
    return letters.generator_infos(generators)


@router.get(
    "/postings/{posting_id}/letter-context", response_model=LetterContextPreview, tags=["letters"]
)
def letter_context(session: SessionDep, posting_id: int) -> LetterContextPreview:
    """Automatisch erkannte Grundlagen (Portal, Hashtags, Beschreibung, passende Skills)."""
    return letters.preview_context(session, posting_id)


@router.get(
    "/postings/{posting_id}/letters", response_model=list[CoverLetterRead], tags=["letters"]
)
def list_letters(session: SessionDep, posting_id: int) -> list[CoverLetterRead]:
    return [letters.to_read(x) for x in letters.list_letters(session, posting_id)]


@router.post(
    "/postings/{posting_id}/letters",
    response_model=CoverLetterRead,
    status_code=status.HTTP_201_CREATED,
    tags=["letters"],
)
def create_letter(
    session: SessionDep,
    generators: LetterGeneratorsDep,
    posting_id: int,
    data: CoverLetterRequest,
) -> CoverLetterRead:
    """Erzeugt eine neue Version. Läuft synchron (Claude braucht ggf. einige Sekunden)."""
    return letters.to_read(letters.generate_letter(session, generators, posting_id, data))


@router.patch("/letters/{letter_id}", response_model=CoverLetterRead, tags=["letters"])
def patch_letter(session: SessionDep, letter_id: int, data: CoverLetterUpdate) -> CoverLetterRead:
    return letters.to_read(letters.update_letter(session, letter_id, data))


# --- Unterlagen ----------------------------------------------------------------

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
    doc = documents.upload(
        session,
        store,
        data=b"".join(chunks),
        filename=file.filename or "dokument",
        kind=kind,
        title=title or None,
    )
    return documents.to_read(doc)


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
    """Unterlagen dieser Bewerbung setzen; Entfernte bleiben mit ``detached_at`` erhalten."""
    docs = documents.set_posting_documents(session, posting_id, data.document_ids)
    return [documents.to_read(d) for d in docs]

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from bewerbung.config import Settings, resolve_documents_dir
from bewerbung.documents.extract import DOCX, PDF, detect_type, extract_text

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_pdf(text: str) -> bytes:
    """Minimales PDF mit einer Textzeile (Helvetica), ohne Zusatzbibliothek."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    )
    return out.getvalue()


def make_docx(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


def upload(client: TestClient, name: str, data: bytes, **form: str):
    return client.post("/api/documents", files={"file": (name, data)}, data=form)


def test_detect_and_extract() -> None:
    pdf = make_pdf("Erfahrung mit Python und SQL")
    assert detect_type(pdf, "x.bin") is PDF
    assert "Python und SQL" in (extract_text(pdf, PDF).text or "")
    docx = make_docx("Max Muster", "Data Scientist")
    assert detect_type(docx, "cv.docx") is DOCX
    assert extract_text(docx, DOCX).text == "Max Muster\nData Scientist"
    bom = "\ufeffLebenslauf".encode()
    assert extract_text(bom, detect_type(bom, "cv.txt")).text == "Lebenslauf"


def test_documents_dir_next_to_database(settings: Settings) -> None:
    db_file = Path(settings.database_url.removeprefix("sqlite:///"))
    assert resolve_documents_dir(settings) == db_file.parent / "documents"


def test_upload_cv_becomes_primary_and_feeds_letters(
    client: TestClient, settings: Settings, make_posting
) -> None:
    resp = upload(client, "Lebenslauf_Max.pdf", make_pdf("Python SQL Machine Learning"))
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["kind"] == "lebenslauf"
    assert doc["is_primary"] is True
    assert doc["has_text"] is True
    assert doc["title"] == "Lebenslauf Max"
    assert doc["page_count"] == 1
    stored = list(resolve_documents_dir(settings).iterdir())
    assert [p.suffix for p in stored] == [".pdf"]

    # Gleiche Datei erneut -> 409 mit Verweis
    dup = upload(client, "kopie.pdf", make_pdf("Python SQL Machine Learning"))
    assert dup.status_code == 409
    assert dup.json()["existing_id"] == doc["id"]

    # Download liefert genau die Datei, inline als PDF
    file = client.get(f"/api/documents/{doc['id']}/file")
    assert file.status_code == 200
    assert file.headers["content-type"] == "application/pdf"
    assert file.headers["content-disposition"].startswith("inline")
    assert file.content.startswith(b"%PDF-")

    # Ohne Lebenslauf-Text im Profil nutzt der Anschreiben-Kontext den Haupt-Lebenslauf
    client.put("/api/profile", json={"full_name": "Max", "headline": "Data Scientist"})
    p = make_posting(description="Wir suchen Python-Erfahrung.")
    ctx = client.get(f"/api/postings/{p['id']}/letter-context").json()
    assert "Über mich oder Lebenslauf" not in ctx["missing_profile_fields"]
    letter = client.post(f"/api/postings/{p['id']}/letters", json={"generator": "template"})
    assert "Python SQL" in letter.json()["input_snapshot"]["cv_text"]

    # Text ins Profil übernehmen
    prof = client.post(f"/api/documents/{doc['id']}/use-as-cv").json()
    assert "Machine Learning" in prof["cv_text"]


def test_rejects_unsupported_and_oversized(client: TestClient) -> None:
    resp = upload(client, "virus.exe", b"MZ\x90\x00binary")
    assert resp.status_code == 400
    assert "Erlaubt sind" in resp.json()["detail"]
    old_word = upload(client, "alt.doc", b"\xd0\xcf\x11\xe0 old word")
    assert ".docx" in old_word.json()["detail"]
    client.app.state.max_upload_bytes = 10  # type: ignore[attr-defined]
    big = upload(client, "gross.txt", b"x" * 11)
    assert big.status_code == 400
    assert "größer" in big.json()["detail"]


def test_kinds_primary_archive_and_filename_sanitized(client: TestClient) -> None:
    a = upload(client, "../../etc/CV alt.docx", make_docx("Alt")).json()
    b = upload(client, "zeugnis.txt", b"Sehr gut").json()
    assert a["filename"] == "CV alt.docx"
    assert b["kind"] == "zeugnis"
    assert b["is_primary"] is False

    # Zeugnis kann kein Haupt-Lebenslauf sein
    bad = client.patch(f"/api/documents/{b['id']}", json={"is_primary": True})
    assert bad.status_code == 400

    c = upload(client, "lebenslauf-neu.docx", make_docx("Neu"), kind="lebenslauf").json()
    assert c["is_primary"] is False
    client.patch(f"/api/documents/{c['id']}", json={"is_primary": True})
    primaries = [d["id"] for d in client.get("/api/documents").json() if d["is_primary"]]
    assert primaries == [c["id"]]

    client.post(f"/api/documents/{a['id']}/archive")
    ids = [d["id"] for d in client.get("/api/documents").json()]
    assert a["id"] not in ids
    all_ids = [d["id"] for d in client.get("/api/documents?include_archived=true").json()]
    assert a["id"] in all_ids
    # Archivierte Datei darf erneut hochgeladen werden
    assert upload(client, "CV alt.docx", make_docx("Alt")).status_code == 201


def test_posting_documents_keep_history(client: TestClient, make_posting) -> None:
    p = make_posting()
    cv = upload(client, "cv.txt", b"CV").json()
    cert = upload(client, "zertifikat.txt", b"AWS").json()
    url = f"/api/postings/{p['id']}/documents"
    assert [
        d["id"] for d in client.put(url, json={"document_ids": [cv["id"], cert["id"]]}).json()
    ] == [
        cv["id"],
        cert["id"],
    ]
    assert [d["id"] for d in client.put(url, json={"document_ids": [cert["id"]]}).json()] == [
        cert["id"]
    ]
    assert client.put(url, json={"document_ids": [999]}).status_code == 404

    from sqlalchemy import select  # noqa: PLC0415

    from bewerbung.db.models import PostingDocument  # noqa: PLC0415

    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as s:
        links = s.scalars(select(PostingDocument).order_by(PostingDocument.id)).all()
        assert [(lnk.document_id, lnk.ended_at is None) for lnk in links] == [
            (cv["id"], False),
            (cert["id"], True),
        ]

"""Prompt für Anschreiben. Bei inhaltlichen Änderungen PROMPT_VERSION erhöhen."""

from __future__ import annotations

from bewerbung.letters.base import LENGTH_WORDS, LetterContext

PROMPT_VERSION = "p1"

SYSTEM_PROMPT = """\
Du schreibst Anschreiben für Bewerbungen auf Deutsch, im Namen der Person, deren Profil \
du bekommst. Ziel ist ein Text, den sie nach kurzem Gegenlesen verschicken kann.

So gehst du vor:
- Lies die Stellenbeschreibung und arbeite die zwei bis drei wichtigsten Anforderungen \
heraus. Verbinde jede davon mit einer konkreten Erfahrung oder Fähigkeit aus dem Profil \
oder Lebenslauf.
- Verwende ausschließlich Fakten aus Profil, Lebenslauf und Hinweisen. Erfinde keine \
Arbeitgeber, Abschlüsse, Zahlen oder Erfolge. Fehlt etwas, lass es weg, statt es zu \
umschreiben oder Platzhalter wie [Name] einzusetzen.
- Die Hashtags sind Stichworte, mit denen die Person die Stelle eingeordnet hat. Nutze sie \
als Hinweis auf Schwerpunkte, nicht als Wörter, die im Text vorkommen müssen.
- Wenn das Portal bekannt ist, darfst du einmal natürlich erwähnen, wo die Anzeige stand.
- Vermeide Floskeln wie "hiermit bewerbe ich mich" oder "mit großem Interesse", \
Aufzählungszeichen und Übertreibungen. Schreibe aktiv und konkret.

Ausgabe: nur das Anschreiben als reiner Text ohne Markdown, in dieser Reihenfolge: eine \
Zeile "Betreff: ...", die Anrede, der Brieftext in Absätzen, die Grußformel und darunter \
die Signatur bzw. der Name. Keine Adresszeilen, kein Datum, keine Erklärungen davor \
oder danach."""

_TONE = {
    "formell": "formell und sachlich, klassische Anrede und Grußformel",
    "modern": "professionell, aber zugewandt und direkt",
    "locker": "locker und persönlich (passend z. B. für Start-ups), trotzdem respektvoll",
}


def _section(tag: str, value: str | None) -> str:
    return f"<{tag}>\n{value.strip()}\n</{tag}>" if value and value.strip() else ""


def build_user_prompt(ctx: LetterContext) -> str:
    stelle = "\n".join(
        line
        for line in (
            f"Titel: {ctx.title}",
            f"Unternehmen: {ctx.company}" if ctx.company else "",
            f"Ort: {ctx.location}" if ctx.location else "",
            f"Arbeitsmodell: {ctx.remote}" if ctx.remote else "",
            f"Anstellung: {ctx.employment_type}" if ctx.employment_type else "",
            f"Portal: {ctx.portal}" if ctx.portal else "",
            f"Ansprechperson: {ctx.contact_name}" if ctx.contact_name else "",
        )
        if line
    )
    profil = "\n".join(
        line
        for line in (
            f"Name: {ctx.applicant_name}" if ctx.applicant_name else "",
            f"Kurzprofil: {ctx.applicant_headline}" if ctx.applicant_headline else "",
            f"Fähigkeiten: {', '.join(ctx.applicant_skills)}" if ctx.applicant_skills else "",
            f"Über mich:\n{ctx.applicant_summary}" if ctx.applicant_summary else "",
        )
        if line
    )
    parts = [
        _section("stelle", stelle),
        _section("hashtags", " ".join(f"#{t}" for t in ctx.tags)),
        _section("stellenbeschreibung", ctx.description),
        _section("profil", profil),
        _section("lebenslauf", ctx.cv_text),
        _section("signatur", ctx.signature),
        _section("hinweise_der_person", ctx.extra_notes),
        f"Tonfall: {_TONE[ctx.tone]}. Länge des Brieftexts: {LENGTH_WORDS[ctx.length]}.",
        "Schreibe jetzt das Anschreiben.",
    ]
    return "\n\n".join(p for p in parts if p)

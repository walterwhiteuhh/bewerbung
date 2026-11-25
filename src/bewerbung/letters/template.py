"""Anschreiben aus Textbausteinen: läuft lokal, ohne Key, als Ersatz für die Claude-API."""

from __future__ import annotations

from bewerbung.letters.base import GeneratedLetter, LetterContext

TEMPLATE_VERSION = "t1"


def _greeting(ctx: LetterContext) -> str:
    if ctx.contact_name:
        return f"Guten Tag {ctx.contact_name},"
    return "Sehr geehrte Damen und Herren," if ctx.tone == "formell" else "Guten Tag,"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " und " + items[-1]


class TemplateGenerator:
    name = "template"

    @property
    def unavailable_reason(self) -> str | None:
        return None

    def generate(self, ctx: LetterContext) -> GeneratedLetter:
        company = ctx.company or "Ihr Unternehmen"
        where = f" auf {ctx.portal}" if ctx.portal else ""
        paragraphs = [
            f"Betreff: Bewerbung als {ctx.title}",
            _greeting(ctx),
            f"mit großem Interesse habe ich Ihre Stellenanzeige{where} gelesen. "
            f"Die Position als {ctx.title} bei {company} passt sehr gut zu meinem Profil"
            + (f" als {ctx.applicant_headline}" if ctx.applicant_headline else "")
            + ".",
        ]
        if ctx.matching_skills:
            paragraphs.append(
                f"Besonders meine Erfahrung mit {_join(ctx.matching_skills[:5])} "
                "kann ich direkt in Ihre Aufgaben einbringen."
            )
        if ctx.applicant_summary:
            paragraphs.append(ctx.applicant_summary.strip())
        if ctx.extra_notes:
            paragraphs.append(ctx.extra_notes.strip())
        paragraphs.append(
            "Über die Gelegenheit, Sie in einem persönlichen Gespräch von mir zu überzeugen, "
            "freue ich mich sehr."
        )
        closing = "Mit freundlichen Grüßen" if ctx.tone == "formell" else "Viele Grüße"
        if ctx.signature:
            # Eine gepflegte Signatur enthält meist schon die Grußformel.
            paragraphs.append(ctx.signature.strip())
        else:
            paragraphs.append(f"{closing}\n{ctx.applicant_name or ''}".rstrip())
        return GeneratedLetter(body="\n\n".join(paragraphs), generator=self.name)

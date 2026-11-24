from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from bewerbung.db.models import Company

_LEGAL_FORMS = re.compile(r"\b(gmbh|ag|se|kg|ohg|ug|mbh|co|inc|ltd|llc|e\.?v)\b\.?", re.IGNORECASE)


def company_key(name: str) -> str:
    """Normalisierter Vergleichsschlüssel: ohne Rechtsform, Satzzeichen und Mehrfach-Leerzeichen."""
    key = _LEGAL_FORMS.sub(" ", name.casefold())
    key = re.sub(r"[^\w]+", " ", key)
    return " ".join(key.split()) or name.casefold().strip()


def get_or_create_company(session: Session, name: str) -> Company:
    key = company_key(name)
    company = session.scalar(select(Company).where(Company.name_key == key))
    if company is None:
        company = Company(name=name.strip(), name_key=key)
        session.add(company)
        session.flush()
    return company

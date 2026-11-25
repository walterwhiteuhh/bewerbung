"""Hashtag-Verknüpfungen im Hintergrund: Oberbegriffe und Synonyme.

``implies``: A -> B heißt "A ist ein Unterbegriff von B". Wer nach B filtert, findet auch
Stellen mit A (``pandas`` -> ``python``, ``react`` -> ``frontend``). ``alias``: gleichbedeutend.
``related``: nur ein Hinweis ("passt oft dazu"), beeinflusst keine Filter.

Die Startwerte stehen in einer Migration und lassen sich später in der DB ändern.
"""

from __future__ import annotations

# Unterbegriff -> Oberbegriffe
SEED_IMPLIES: dict[str, tuple[str, ...]] = {
    "pandas": ("python", "data-science"),
    "machine-learning": ("ki", "data-science"),
    "llm": ("ki", "nlp"),
    "nlp": ("ki",),
    "spark": ("data-engineering",),
    "power-bi": ("bi",),
    "tableau": ("bi",),
    "react": ("frontend", "javascript"),
    "angular": ("frontend", "typescript"),
    "vue": ("frontend", "javascript"),
    "typescript": ("frontend",),
    "javascript": ("frontend",),
    "node": ("backend", "javascript"),
    "java": ("backend",),
    "dotnet": ("backend",),
    "golang": ("backend",),
    "php": ("backend",),
    "rust": ("backend",),
    "sql": ("datenbanken",),
    "nosql": ("datenbanken",),
    "aws": ("cloud",),
    "azure": ("cloud",),
    "gcp": ("cloud",),
    "docker": ("devops",),
    "kubernetes": ("devops", "cloud"),
    "scrum": ("agil",),
}

# Gleichbedeutende Begriffe (symmetrisch)
SEED_ALIASES: tuple[tuple[str, str], ...] = (
    ("ki", "ai"),
    ("remote", "homeoffice"),
    ("agil", "agile"),
    ("projektmanagement", "project-management"),
    ("golang", "go"),
)

# Lose Zusammenhänge (nur Vorschläge)
SEED_RELATED: tuple[tuple[str, str], ...] = (
    ("data-science", "python"),
    ("devops", "linux"),
    ("backend", "datenbanken"),
    ("consulting", "projektmanagement"),
)

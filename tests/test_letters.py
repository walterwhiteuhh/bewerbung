from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.domain.enums import RemoteType
from bewerbung.domain.keywords import suggest_tags
from bewerbung.letters.base import GeneratedLetter, GenerationError, LetterContext
from bewerbung.letters.claude import ClaudeGenerator
from bewerbung.letters.gemini import GeminiGenerator
from bewerbung.letters.openai_gen import OpenAIGenerator
from bewerbung.letters.prompt import build_user_prompt
from bewerbung.letters.registry import build_generators
from bewerbung.letters.template import TemplateGenerator
from bewerbung.main import create_app
from bewerbung.services.letters import _matching_skills

DESCRIPTION = (
    "Du entwickelst Machine-Learning-Modelle mit Python und SQL, betreibst sie auf AWS "
    "und arbeitest agil im Team."
)


class RecordingGenerator:
    """Wie der Claude-Generator, aber ohne Netzwerk: merkt sich den Kontext."""

    name = "claude"
    model = "fake-model"

    def __init__(self, fail: bool = False) -> None:
        self.contexts: list[LetterContext] = []
        self.fail = fail

    @property
    def unavailable_reason(self) -> str | None:
        return None

    def generate(self, ctx: LetterContext) -> GeneratedLetter:
        self.contexts.append(ctx)
        if self.fail:
            raise GenerationError("kaputt")
        return GeneratedLetter(
            body=f"Betreff: Bewerbung als {ctx.title}\n\nText",
            generator=self.name,
            model=self.model,
            input_tokens=1000,
            output_tokens=400,
        )


@pytest.fixture
def fake() -> RecordingGenerator:
    return RecordingGenerator()


@pytest.fixture
def lclient(settings: Settings, fake: RecordingGenerator) -> Iterator[TestClient]:
    gens = {"claude": fake, "template": TemplateGenerator()}
    with TestClient(create_app(settings, letter_generators=gens)) as c:
        yield c


def _posting(c: TestClient, **extra: object) -> dict[str, Any]:
    payload: dict[str, object] = {
        "title": "Data Scientist (m/w/d)",
        "company_name": "ACME GmbH",
        "url": "https://www.stepstone.de/stellenangebote--Data-Scientist-Hamburg-ACME--1234567-inline.html",
        "location": "Hamburg",
        "remote_type": "hybrid",
        "description": DESCRIPTION,
    }
    payload.update(extra)
    resp = c.post("/api/postings", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_suggest_tags_from_description() -> None:
    tags = suggest_tags(
        title="Senior Data Scientist",
        description=DESCRIPTION,
        location="20095 Hamburg, Hamburg",
        remote_type=RemoteType.HYBRID,
    )
    assert tags[:3] == ["senior", "hybrid", "hamburg"]
    assert {"python", "sql", "aws", "machine-learning", "data-science"} <= set(tags)
    assert "java" not in suggest_tags(title="JavaScript Dev", description="JavaScript")


def test_profile_roundtrip(lclient: TestClient) -> None:
    assert lclient.get("/api/profile").json()["full_name"] is None
    resp = lclient.put(
        "/api/profile",
        json={"full_name": "Timo Test", "headline": "Data Scientist", "skills": ["Python", "SQL"]},
    )
    assert resp.status_code == 200
    assert lclient.get("/api/profile").json()["skills"] == ["Python", "SQL"]


def test_context_detects_portal_tags_and_skills(lclient: TestClient) -> None:
    lclient.put("/api/profile", json={"full_name": "Timo", "skills": ["Python", "Excel", "AWS"]})
    p = _posting(lclient)
    ctx = lclient.get(f"/api/postings/{p['id']}/letter-context").json()
    assert ctx["portal"] == "StepStone"
    assert ctx["tags"] == []
    assert "python" in ctx["suggested_tags"]
    assert ctx["matching_skills"] == ["Python", "AWS"]
    assert ctx["profile_complete"] is False
    assert "Kurzprofil" in ctx["missing_profile_fields"]


def test_generate_versions_and_snapshot(lclient: TestClient, fake: RecordingGenerator) -> None:
    lclient.put("/api/profile", json={"full_name": "Timo", "skills": ["Python"]})
    p = _posting(lclient, tags=["traumjob"])
    lclient.patch(
        f"/api/applications/{p['application']['id']}", json={"contact_name": "Frau Weber"}
    )

    r1 = lclient.post(f"/api/postings/{p['id']}/letters", json={"tone": "formell"})
    assert r1.status_code == 201, r1.text
    l1 = r1.json()
    assert (l1["version"], l1["generator"], l1["model"], l1["status"]) == (
        1,
        "claude",
        "fake-model",
        "draft",
    )
    ctx = fake.contexts[-1]
    assert ctx.portal == "StepStone"
    assert ctx.tags == ["traumjob"]  # gesetzte Hashtags haben Vorrang vor Vorschlägen
    assert ctx.contact_name == "Frau Weber"
    assert l1["input_snapshot"]["tone"] == "formell"

    l2 = lclient.post(f"/api/postings/{p['id']}/letters", json={"generator": "template"}).json()
    assert (l2["version"], l2["generator"]) == (2, "template")
    assert "StepStone" in l2["body"] and "Guten Tag Frau Weber," in l2["body"]

    edited = lclient.patch(
        f"/api/letters/{l1['id']}", json={"body": "Neu", "status": "final"}
    ).json()
    assert edited["edited"] is True and edited["status"] == "final"
    lclient.patch(f"/api/letters/{l2['id']}", json={"status": "final"})
    versions = lclient.get(f"/api/postings/{p['id']}/letters").json()
    assert [(v["version"], v["status"]) for v in versions] == [(2, "final"), (1, "draft")]


def test_generation_errors(settings: Settings) -> None:
    gens = {"claude": RecordingGenerator(fail=True), "template": TemplateGenerator()}
    with TestClient(create_app(settings, letter_generators=gens)) as c:
        p = _posting(c)
        resp = c.post(f"/api/postings/{p['id']}/letters", json={})
        assert resp.status_code == 502
        assert "kaputt" in resp.json()["detail"]
        assert c.get(f"/api/postings/{p['id']}/letters").json() == []


def test_auto_falls_back_to_template_without_key(settings: Settings) -> None:
    gens = {"claude": ClaudeGenerator(None, "claude-opus-5-5"), "template": TemplateGenerator()}
    with TestClient(create_app(settings, letter_generators=gens)) as c:
        infos = {g["name"]: g for g in c.get("/api/letters/generators").json()}
        assert infos["claude"]["available"] is False
        p = _posting(c)
        assert c.post(f"/api/postings/{p['id']}/letters", json={}).json()["generator"] == "template"
        resp = c.post(f"/api/postings/{p['id']}/letters", json={"generator": "claude"})
        assert resp.status_code == 400


def _ctx(**overrides: Any) -> LetterContext:
    base: dict[str, Any] = {
        "title": "Data Scientist",
        "company": "ACME",
        "location": "Hamburg",
        "portal": "StepStone",
        "url": None,
        "description": DESCRIPTION,
        "tags": ["python"],
        "employment_type": None,
        "remote": "Hybrid",
        "contact_name": None,
        "applicant_name": "Timo",
        "applicant_headline": None,
        "applicant_summary": None,
        "applicant_skills": ["Python"],
        "cv_text": None,
        "signature": None,
    }
    base.update(overrides)
    return LetterContext(**base)


def test_prompt_contains_context_and_skips_empty_sections() -> None:
    prompt = build_user_prompt(_ctx())
    assert "<stellenbeschreibung>" in prompt and "Portal: StepStone" in prompt
    assert "#python" in prompt
    assert "<lebenslauf>" not in prompt  # leere Abschnitte fehlen ganz


class _FakeMessages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


def _fake_client(stop_reason: str, text: str = "Betreff: X\n\nHallo") -> tuple[Any, _FakeMessages]:
    response = SimpleNamespace(
        stop_reason=stop_reason,
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=1200, output_tokens=350),
    )
    messages = _FakeMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_claude_generator_request_and_response() -> None:
    client, messages = _fake_client("end_turn")
    result = ClaudeGenerator("key", "claude-opus-5-5", client=client).generate(_ctx())
    assert result.body == "Betreff: X\n\nHallo"
    assert (result.input_tokens, result.output_tokens) == (1200, 350)
    sent = messages.kwargs
    assert sent["model"] == "claude-opus-5-5"
    assert sent["fallbacks"] == "default"
    assert sent["output_config"] == {"effort": "medium"}
    assert "Erfinde keine" in sent["system"]


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_claude_generator_rejects_incomplete(stop_reason: str) -> None:
    client, _ = _fake_client(stop_reason)
    with pytest.raises(GenerationError):
        ClaudeGenerator("key", "m", client=client).generate(_ctx())


# --- OpenAI / Gemini über httpx.MockTransport ---------------------------------


def _mock_client(status: int, body: dict[str, Any], seen: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_generator_request_and_response() -> None:
    seen: list[httpx.Request] = []
    body = {
        "model": "gpt-5-2025",
        "choices": [{"finish_reason": "stop", "message": {"content": "Betreff: X\n\nHallo"}}],
        "usage": {"prompt_tokens": 900, "completion_tokens": 300},
    }
    gen = OpenAIGenerator("sk-test", "gpt-5", client=_mock_client(200, body, seen))
    result = gen.generate(_ctx())
    assert (result.body, result.generator, result.model) == (
        "Betreff: X\n\nHallo",
        "openai",
        "gpt-5-2025",
    )
    assert (result.input_tokens, result.output_tokens) == (900, 300)
    req = seen[0]
    assert req.headers["authorization"] == "Bearer sk-test"
    sent = json.loads(req.content)
    assert sent["model"] == "gpt-5"
    assert sent["messages"][0]["role"] == "system"
    assert "Erfinde keine" in sent["messages"][0]["content"]


@pytest.mark.parametrize(
    ("status", "body", "match"),
    [
        (401, {"error": {}}, "ungültig"),
        (429, {"error": {}}, "Zu viele"),
        (
            200,
            {"choices": [{"finish_reason": "length", "message": {"content": "Hal"}}]},
            "vollständig",
        ),
        (200, {"choices": [{"message": {"content": None, "refusal": "nein"}}]}, "abgelehnt"),
    ],
)
def test_openai_generator_errors(status: int, body: dict[str, Any], match: str) -> None:
    gen = OpenAIGenerator("sk-test", "gpt-5", client=_mock_client(status, body, []))
    with pytest.raises(GenerationError, match=match):
        gen.generate(_ctx())


def test_gemini_generator_request_and_response() -> None:
    seen: list[httpx.Request] = []
    body = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": "intern", "thought": True}, {"text": "Betreff: Y"}]},
            }
        ],
        "usageMetadata": {"promptTokenCount": 800, "candidatesTokenCount": 250},
        "modelVersion": "gemini-2.5-pro",
    }
    gen = GeminiGenerator("g-key", "gemini-2.5-pro", client=_mock_client(200, body, seen))
    result = gen.generate(_ctx())
    assert (result.body, result.generator) == ("Betreff: Y", "gemini")
    assert (result.input_tokens, result.output_tokens) == (800, 250)
    req = seen[0]
    assert req.url.path.endswith("/models/gemini-2.5-pro:generateContent")
    assert req.headers["x-goog-api-key"] == "g-key"
    assert "key=" not in str(req.url)
    sent = json.loads(req.content)
    assert "Erfinde keine" in sent["systemInstruction"]["parts"][0]["text"]


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "abgelehnt"),
        ({"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}, "abgelehnt"),
        (
            {
                "candidates": [
                    {"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "Ha"}]}}
                ]
            },
            "vollständig",
        ),
    ],
)
def test_gemini_generator_errors(body: dict[str, Any], match: str) -> None:
    gen = GeminiGenerator("g-key", "gemini-2.5-pro", client=_mock_client(200, body, []))
    with pytest.raises(GenerationError, match=match):
        gen.generate(_ctx())


def test_registry_lists_all_providers_and_auto_prefers_first_with_key() -> None:
    settings = Settings(database_url="sqlite://", gemini_api_key="g-key")
    gens = build_generators(settings)
    assert list(gens) == ["claude", "openai", "gemini", "template"]
    assert [n for n, g in gens.items() if g.unavailable_reason is None] == ["gemini", "template"]


def test_matching_skills_treats_space_and_hyphen_alike() -> None:
    text = "Du baust Machine-Learning-Modelle mit Python."
    assert _matching_skills(["Machine Learning", "Python", "Java"], ["sql"], text) == [
        "Machine Learning",
        "Python",
    ]
    assert _matching_skills(["Data Science"], ["data-science"], "") == ["Data Science"]

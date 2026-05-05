import json
import pytest

from agents.classifier_agent import ClassifierAgent
from config import VALID_CATEGORIES

MODEL = "anthropic/claude-sonnet-4-6"

ITEM = {"id": "T1", "source_type": "review", "text": "The app crashes on login."}


@pytest.fixture
def agent():
    return ClassifierAgent(model=MODEL)


def _patch_invoke(monkeypatch, data: dict):
    async def fake(agent_obj, prompt):
        return json.dumps(data)
    monkeypatch.setattr("agents.classifier_agent._invoke_agent", fake)


@pytest.mark.asyncio
async def test_returns_valid_category(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"category": "Bug", "confidence": 0.95})
    out = await agent.classify(ITEM)
    assert out.category == "Bug"
    assert out.confidence == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_all_valid_categories(monkeypatch, agent):
    for cat in VALID_CATEGORIES:
        _patch_invoke(monkeypatch, {"category": cat, "confidence": 0.8})
        out = await agent.classify(ITEM)
        assert out.category == cat


@pytest.mark.asyncio
async def test_invalid_category_defaults_to_complaint(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"category": "Unknown", "confidence": 0.5})
    out = await agent.classify(ITEM)
    assert out.category == "Complaint"


@pytest.mark.asyncio
async def test_confidence_clamped_above_one(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"category": "Bug", "confidence": 1.5})
    out = await agent.classify(ITEM)
    assert out.confidence == 1.0


@pytest.mark.asyncio
async def test_confidence_clamped_below_zero(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"category": "Spam", "confidence": -0.3})
    out = await agent.classify(ITEM)
    assert out.confidence == 0.0


@pytest.mark.asyncio
async def test_strips_markdown_fence(monkeypatch, agent):
    async def fake(agent_obj, prompt):
        return '```json\n{"category": "Feature Request", "confidence": 0.9}\n```'
    monkeypatch.setattr("agents.classifier_agent._invoke_agent", fake)
    out = await agent.classify(ITEM)
    assert out.category == "Feature Request"


@pytest.mark.asyncio
async def test_item_text_passed_to_agent(monkeypatch, agent):
    captured = []

    async def capture(agent_obj, prompt):
        captured.append(prompt)
        return json.dumps({"category": "Bug", "confidence": 0.9})

    monkeypatch.setattr("agents.classifier_agent._invoke_agent", capture)
    await agent.classify({"id": "R1", "source_type": "review", "text": "unique crash xyz"})
    assert "unique crash xyz" in captured[0]

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.classifier_agent import ClassifierAgent
from config import VALID_CATEGORIES

ITEM = {"id": "T1", "source_type": "review", "text": "The app crashes on login."}


@pytest.fixture
def agent():
    return ClassifierAgent(model_client=MagicMock())


def _patch_run(agent, category, confidence):
    msg = MagicMock()
    msg.content = json.dumps({"category": category, "confidence": confidence})
    result = MagicMock()
    result.messages = [msg]
    agent._agent.run = AsyncMock(return_value=result)


@pytest.mark.asyncio
async def test_returns_valid_category(agent):
    _patch_run(agent, "Bug", 0.95)
    out = await agent.classify(ITEM)
    assert out.category == "Bug"
    assert out.confidence == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_all_valid_categories(agent):
    for cat in VALID_CATEGORIES:
        _patch_run(agent, cat, 0.8)
        out = await agent.classify(ITEM)
        assert out.category == cat


@pytest.mark.asyncio
async def test_invalid_category_defaults_to_complaint(agent):
    _patch_run(agent, "Unknown", 0.5)
    out = await agent.classify(ITEM)
    assert out.category == "Complaint"


@pytest.mark.asyncio
async def test_confidence_clamped_above_one(agent):
    _patch_run(agent, "Bug", 1.5)
    out = await agent.classify(ITEM)
    assert out.confidence == 1.0


@pytest.mark.asyncio
async def test_confidence_clamped_below_zero(agent):
    _patch_run(agent, "Spam", -0.3)
    out = await agent.classify(ITEM)
    assert out.confidence == 0.0


@pytest.mark.asyncio
async def test_strips_markdown_fence(agent):
    msg = MagicMock()
    msg.content = '```json\n{"category": "Feature Request", "confidence": 0.9}\n```'
    result = MagicMock()
    result.messages = [msg]
    agent._agent.run = AsyncMock(return_value=result)
    out = await agent.classify(ITEM)
    assert out.category == "Feature Request"


@pytest.mark.asyncio
async def test_item_text_passed_to_agent(agent):
    captured = []

    async def capture_run(task):
        captured.append(task)
        msg = MagicMock()
        msg.content = json.dumps({"category": "Bug", "confidence": 0.9})
        r = MagicMock()
        r.messages = [msg]
        return r

    agent._agent.run = capture_run
    await agent.classify({"id": "R1", "source_type": "review", "text": "unique crash xyz"})
    assert "unique crash xyz" in captured[0]

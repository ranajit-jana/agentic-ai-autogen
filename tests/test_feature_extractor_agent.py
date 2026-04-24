import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.feature_extractor_agent import FeatureExtractorAgent

SAMPLE = {
    "id": "R006", "source_type": "review",
    "text": "Please add dark mode! Many users want this feature for night-time use.",
}


@pytest.fixture
def agent():
    return FeatureExtractorAgent(model_client=MagicMock())


def _patch_run(agent, feature_description, user_impact, demand_score):
    msg = MagicMock()
    msg.content = json.dumps({
        "feature_description": feature_description,
        "user_impact": user_impact,
        "demand_score": demand_score,
    })
    result = MagicMock()
    result.messages = [msg]
    agent._agent.run = AsyncMock(return_value=result)


@pytest.mark.asyncio
async def test_returns_all_fields(agent):
    _patch_run(agent, "Add dark mode for night-time use", "High", 8)
    out = await agent.extract(SAMPLE)
    assert out.feature_description == "Add dark mode for night-time use"
    assert out.user_impact == "High"
    assert out.demand_score == 8


@pytest.mark.asyncio
async def test_user_impact_high(agent):
    _patch_run(agent, "Dark mode", "High", 9)
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "High"


@pytest.mark.asyncio
async def test_user_impact_medium(agent):
    _patch_run(agent, "Calendar view", "Medium", 6)
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "Medium"


@pytest.mark.asyncio
async def test_user_impact_low(agent):
    _patch_run(agent, "Custom icon", "Low", 3)
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "Low"


@pytest.mark.asyncio
async def test_invalid_user_impact_defaults_to_medium(agent):
    _patch_run(agent, "Some feature", "Very High", 7)
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "Medium"


@pytest.mark.asyncio
async def test_demand_score_clamped_above_10(agent):
    _patch_run(agent, "Feature X", "High", 99)
    out = await agent.extract(SAMPLE)
    assert out.demand_score == 10


@pytest.mark.asyncio
async def test_demand_score_clamped_below_1(agent):
    _patch_run(agent, "Feature X", "Low", -5)
    out = await agent.extract(SAMPLE)
    assert out.demand_score == 1


@pytest.mark.asyncio
async def test_demand_score_in_range(agent):
    _patch_run(agent, "Feature X", "Medium", 7)
    out = await agent.extract(SAMPLE)
    assert 1 <= out.demand_score <= 10


@pytest.mark.asyncio
async def test_item_text_passed_to_agent(agent):
    captured = []

    async def capture_run(task):
        captured.append(task)
        msg = MagicMock()
        msg.content = json.dumps({"feature_description": "f", "user_impact": "Low", "demand_score": 4})
        r = MagicMock()
        r.messages = [msg]
        return r

    agent._agent.run = capture_run
    await agent.extract({"id": "E1", "source_type": "email", "text": "please add widget xyz feature"})
    assert "please add widget xyz feature" in captured[0]

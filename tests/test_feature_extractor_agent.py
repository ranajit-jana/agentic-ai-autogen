import json
import pytest

from agents.feature_extractor_agent import FeatureExtractorAgent

MODEL = "anthropic/claude-sonnet-4-6"

SAMPLE = {
    "id": "R006", "source_type": "review",
    "text": "Please add dark mode! Many users want this feature for night-time use.",
}


@pytest.fixture
def agent():
    return FeatureExtractorAgent(model=MODEL)


def _patch_invoke(monkeypatch, data: dict):
    async def fake(agent_obj, prompt):
        return json.dumps(data)
    monkeypatch.setattr("agents.feature_extractor_agent._invoke_agent", fake)


@pytest.mark.asyncio
async def test_returns_all_fields(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Add dark mode for night-time use",
                                "user_impact": "High", "demand_score": 8})
    out = await agent.extract(SAMPLE)
    assert out.feature_description == "Add dark mode for night-time use"
    assert out.user_impact == "High"
    assert out.demand_score == 8


@pytest.mark.asyncio
async def test_user_impact_high(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Dark mode", "user_impact": "High",
                                "demand_score": 9})
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "High"


@pytest.mark.asyncio
async def test_user_impact_medium(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Calendar view", "user_impact": "Medium",
                                "demand_score": 6})
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "Medium"


@pytest.mark.asyncio
async def test_user_impact_low(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Custom icon", "user_impact": "Low",
                                "demand_score": 3})
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "Low"


@pytest.mark.asyncio
async def test_invalid_user_impact_defaults_to_medium(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Some feature", "user_impact": "Very High",
                                "demand_score": 7})
    out = await agent.extract(SAMPLE)
    assert out.user_impact == "Medium"


@pytest.mark.asyncio
async def test_demand_score_clamped_above_10(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Feature X", "user_impact": "High",
                                "demand_score": 99})
    out = await agent.extract(SAMPLE)
    assert out.demand_score == 10


@pytest.mark.asyncio
async def test_demand_score_clamped_below_1(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Feature X", "user_impact": "Low",
                                "demand_score": -5})
    out = await agent.extract(SAMPLE)
    assert out.demand_score == 1


@pytest.mark.asyncio
async def test_demand_score_in_range(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"feature_description": "Feature X", "user_impact": "Medium",
                                "demand_score": 7})
    out = await agent.extract(SAMPLE)
    assert 1 <= out.demand_score <= 10


@pytest.mark.asyncio
async def test_item_text_passed_to_agent(monkeypatch, agent):
    captured = []

    async def capture(agent_obj, prompt):
        captured.append(prompt)
        return json.dumps({"feature_description": "f", "user_impact": "Low", "demand_score": 4})

    monkeypatch.setattr("agents.feature_extractor_agent._invoke_agent", capture)
    await agent.extract({"id": "E1", "source_type": "email",
                         "text": "please add widget xyz feature"})
    assert "please add widget xyz feature" in captured[0]

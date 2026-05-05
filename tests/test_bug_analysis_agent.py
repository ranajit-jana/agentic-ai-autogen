import json
import pytest

from agents.bug_analysis_agent import BugAnalysisAgent

MODEL = "anthropic/claude-sonnet-4-6"

SAMPLE = {
    "id": "R001", "source_type": "review",
    "text": "App crashes on Android 13 when I tap the sync button.",
}


@pytest.fixture
def agent():
    return BugAnalysisAgent(model=MODEL)


def _patch_invoke(monkeypatch, data: dict):
    async def fake(agent_obj, prompt):
        return json.dumps(data)
    monkeypatch.setattr("agents.bug_analysis_agent._invoke_agent", fake)


@pytest.mark.asyncio
async def test_returns_all_fields(monkeypatch, agent):
    _patch_invoke(monkeypatch, {
        "platform": "Android 13", "os_version": "13",
        "steps_to_reproduce": "1) Open 2) Tap sync 3) Crash", "severity": "High",
    })
    out = await agent.analyze(SAMPLE)
    assert out.platform == "Android 13"
    assert out.os_version == "13"
    assert out.steps_to_reproduce == "1) Open 2) Tap sync 3) Crash"
    assert out.severity == "High"


@pytest.mark.asyncio
async def test_severity_critical(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"platform": "Android 14", "os_version": "14",
                                "steps_to_reproduce": "Tap sync", "severity": "Critical"})
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Critical"


@pytest.mark.asyncio
async def test_severity_medium(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"platform": "Windows 11", "os_version": "11",
                                "steps_to_reproduce": "Widget not refreshing", "severity": "Medium"})
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Medium"


@pytest.mark.asyncio
async def test_severity_low(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"platform": "iOS 16", "os_version": "16",
                                "steps_to_reproduce": "Minor UI glitch", "severity": "Low"})
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Low"


@pytest.mark.asyncio
async def test_invalid_severity_defaults_to_medium(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"platform": "iOS 17", "os_version": "17",
                                "steps_to_reproduce": "Not specified", "severity": "Unknown"})
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Medium"


@pytest.mark.asyncio
async def test_unknown_platform_preserved(monkeypatch, agent):
    _patch_invoke(monkeypatch, {"platform": "Unknown", "os_version": "Unknown",
                                "steps_to_reproduce": "Not specified", "severity": "Low"})
    out = await agent.analyze(SAMPLE)
    assert out.platform == "Unknown"


@pytest.mark.asyncio
async def test_item_text_passed_to_agent(monkeypatch, agent):
    captured = []

    async def capture(agent_obj, prompt):
        captured.append(prompt)
        return json.dumps({"platform": "iOS", "os_version": "17",
                           "steps_to_reproduce": "step 1", "severity": "High"})

    monkeypatch.setattr("agents.bug_analysis_agent._invoke_agent", capture)
    await agent.analyze({"id": "R1", "source_type": "review", "text": "unique crash text xyz"})
    assert "unique crash text xyz" in captured[0]

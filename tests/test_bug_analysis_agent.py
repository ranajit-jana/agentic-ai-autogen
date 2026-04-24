import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.bug_analysis_agent import BugAnalysisAgent

SAMPLE = {
    "id": "R001", "source_type": "review",
    "text": "App crashes on Android 13 when I tap the sync button.",
}


@pytest.fixture
def agent():
    return BugAnalysisAgent(model_client=MagicMock())


def _patch_run(agent, platform, os_version, steps, severity):
    msg = MagicMock()
    msg.content = json.dumps({
        "platform": platform,
        "os_version": os_version,
        "steps_to_reproduce": steps,
        "severity": severity,
    })
    result = MagicMock()
    result.messages = [msg]
    agent._agent.run = AsyncMock(return_value=result)


@pytest.mark.asyncio
async def test_returns_all_fields(agent):
    _patch_run(agent, "Android 13", "13", "1) Open 2) Tap sync 3) Crash", "High")
    out = await agent.analyze(SAMPLE)
    assert out.platform == "Android 13"
    assert out.os_version == "13"
    assert out.steps_to_reproduce == "1) Open 2) Tap sync 3) Crash"
    assert out.severity == "High"


@pytest.mark.asyncio
async def test_severity_critical(agent):
    _patch_run(agent, "Android 14", "14", "Tap sync", "Critical")
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Critical"


@pytest.mark.asyncio
async def test_severity_medium(agent):
    _patch_run(agent, "Windows 11", "11", "Widget not refreshing", "Medium")
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Medium"


@pytest.mark.asyncio
async def test_severity_low(agent):
    _patch_run(agent, "iOS 16", "16", "Minor UI glitch", "Low")
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Low"


@pytest.mark.asyncio
async def test_invalid_severity_defaults_to_medium(agent):
    _patch_run(agent, "iOS 17", "17", "Not specified", "Unknown")
    out = await agent.analyze(SAMPLE)
    assert out.severity == "Medium"


@pytest.mark.asyncio
async def test_unknown_platform_preserved(agent):
    _patch_run(agent, "Unknown", "Unknown", "Not specified", "Low")
    out = await agent.analyze(SAMPLE)
    assert out.platform == "Unknown"


@pytest.mark.asyncio
async def test_item_text_passed_to_agent(agent):
    captured = []

    async def capture_run(task):
        captured.append(task)
        msg = MagicMock()
        msg.content = json.dumps({"platform": "iOS", "os_version": "17",
                                   "steps_to_reproduce": "step 1", "severity": "High"})
        r = MagicMock()
        r.messages = [msg]
        return r

    agent._agent.run = capture_run
    await agent.analyze({"id": "R1", "source_type": "review", "text": "unique crash text xyz"})
    assert "unique crash text xyz" in captured[0]

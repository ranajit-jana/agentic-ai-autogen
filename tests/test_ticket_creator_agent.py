import json
import os
import pytest

from agents.ticket_creator_agent import (
    TicketCreatorAgent,
    _derive_priority,
    _build_technical_details,
    ensure_csv,
    next_ticket_id,
)

MODEL = "anthropic/claude-sonnet-4-6"

BUG_STATE = {
    "id": "R001", "source_type": "review",
    "category": "Bug", "confidence": 0.99,
    "text": "App crashes on sync.",
    "platform": "Android 14", "os_version": "14",
    "steps_to_reproduce": "Tap sync > crash",
    "severity": "Critical",
    "retry_count": 0, "quality_issues": [],
}

FEATURE_STATE = {
    "id": "R006", "source_type": "review",
    "category": "Feature Request", "confidence": 0.97,
    "text": "Please add dark mode.",
    "feature_description": "Add dark mode toggle.",
    "user_impact": "High", "demand_score": 9,
    "retry_count": 0, "quality_issues": [],
}


@pytest.fixture
def agent():
    return TicketCreatorAgent(model=MODEL)


def _patch_invoke(monkeypatch, title, description):
    async def fake(agent_obj, prompt):
        return json.dumps({"title": title, "description": description})
    monkeypatch.setattr("agents.ticket_creator_agent._invoke_agent", fake)


@pytest.mark.asyncio
async def test_create_returns_required_keys(monkeypatch, agent):
    _patch_invoke(monkeypatch, "Fix sync crash on Android 14",
                  "**Summary:** Crash.\n**Details:** Steps.\n**User Impact:** High.")
    result = await agent.create(BUG_STATE)
    for key in ("title", "description", "priority", "technical_details", "created_at"):
        assert key in result


@pytest.mark.asyncio
async def test_title_truncated_to_80_chars(monkeypatch, agent):
    _patch_invoke(monkeypatch, "Fix " + "x" * 100,
                  "**Summary:** x.\n**Details:** y.\n**User Impact:** z.")
    result = await agent.create(BUG_STATE)
    assert len(result["title"]) <= 80


@pytest.mark.asyncio
async def test_retry_hint_included_when_retry_count_gt_0(monkeypatch, agent):
    state = {**BUG_STATE, "retry_count": 1, "quality_issues": ["Title too generic"]}
    captured = []

    async def capture(agent_obj, prompt):
        captured.append(prompt)
        return json.dumps({"title": "Fix sync crash on Android", "description": "x"})

    monkeypatch.setattr("agents.ticket_creator_agent._invoke_agent", capture)
    await agent.create(state)
    assert "Title too generic" in captured[0]


@pytest.mark.asyncio
async def test_no_retry_hint_on_first_attempt(monkeypatch, agent):
    captured = []

    async def capture(agent_obj, prompt):
        captured.append(prompt)
        return json.dumps({"title": "Fix sync crash", "description": "x"})

    monkeypatch.setattr("agents.ticket_creator_agent._invoke_agent", capture)
    await agent.create(BUG_STATE)
    assert "PREVIOUS ATTEMPT" not in captured[0]


class TestDerivePriority:
    def test_bug_severity_maps_to_priority(self):
        for sev in ("Critical", "High", "Medium", "Low"):
            assert _derive_priority({"category": "Bug", "severity": sev}) == sev

    def test_bug_defaults_high_when_no_severity(self):
        assert _derive_priority({"category": "Bug"}) == "High"

    def test_feature_high_when_demand_gte_8(self):
        assert _derive_priority({"category": "Feature Request", "demand_score": 8}) == "High"
        assert _derive_priority({"category": "Feature Request", "demand_score": 10}) == "High"

    def test_feature_medium_when_demand_5_to_7(self):
        assert _derive_priority({"category": "Feature Request", "demand_score": 5}) == "Medium"
        assert _derive_priority({"category": "Feature Request", "demand_score": 7}) == "Medium"

    def test_feature_low_when_demand_lt_5(self):
        assert _derive_priority({"category": "Feature Request", "demand_score": 4}) == "Low"

    def test_complaint_defaults_low(self):
        assert _derive_priority({"category": "Complaint"}) == "Low"

    def test_praise_defaults_low(self):
        assert _derive_priority({"category": "Praise"}) == "Low"


class TestBuildTechnicalDetails:
    def test_bug_includes_platform_steps_severity(self):
        details = _build_technical_details(BUG_STATE)
        assert "Android 14" in details
        assert "Tap sync" in details
        assert "Critical" in details

    def test_feature_includes_impact_and_score(self):
        details = _build_technical_details(FEATURE_STATE)
        assert "High" in details
        assert "9/10" in details

    def test_unknown_platform_excluded(self):
        state = {**BUG_STATE, "platform": "Unknown", "os_version": "Unknown"}
        details = _build_technical_details(state)
        assert "Unknown" not in details

    def test_not_specified_steps_excluded(self):
        state = {**BUG_STATE, "steps_to_reproduce": "Not specified"}
        details = _build_technical_details(state)
        assert "Not specified" not in details


class TestCsvUtils:
    def test_next_ticket_id_increments(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agents.ticket_creator_agent._COUNTER_FILE", str(tmp_path / ".counter"))
        import agents.ticket_creator_agent as mod
        mod._COUNTER_FILE = str(tmp_path / ".counter")
        assert mod.next_ticket_id() == "T0001"
        assert mod.next_ticket_id() == "T0002"

    def test_ensure_csv_creates_file(self, tmp_path, monkeypatch):
        csv_path = str(tmp_path / "tickets.csv")
        monkeypatch.setattr("agents.ticket_creator_agent.TICKETS_FILE", csv_path)
        import agents.ticket_creator_agent as mod
        mod.TICKETS_FILE = csv_path
        mod.ensure_csv()
        assert os.path.exists(csv_path)

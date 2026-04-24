import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.quality_critic_agent import QualityCriticAgent

COMPLETE_BUG = {
    "source_id": "R001", "source_type": "review",
    "title": "Fix sync crash on Android 14",
    "description": "**Summary:** App crashes.\n**Details:** Tap sync then crash.\n**User Impact:** Cannot sync.",
    "category": "Bug", "priority": "High",
    "technical_details": "Platform: Android 14 | Steps: tap sync | Severity: High",
}

COMPLETE_FEATURE = {
    "source_id": "R006", "source_type": "review",
    "title": "Add dark mode support for night usage",
    "description": "**Summary:** Dark mode needed.\n**Details:** Many users request it.\n**User Impact:** Reduces eye strain.",
    "category": "Feature Request", "priority": "Medium",
    "technical_details": "",
}


@pytest.fixture
def agent():
    return QualityCriticAgent(model_client=None)  # local rule-based, no LLM


class TestReviewLocally:
    def test_complete_bug_passes(self, agent):
        result = agent.review_locally(COMPLETE_BUG)
        assert result["passed"] is True
        assert result["issues"] == []

    def test_complete_feature_passes(self, agent):
        result = agent.review_locally(COMPLETE_FEATURE)
        assert result["passed"] is True

    def test_missing_title_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "title": ""})
        assert result["passed"] is False
        assert any("title" in i.lower() for i in result["issues"])

    def test_whitespace_only_title_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "title": "   "})
        assert result["passed"] is False

    def test_title_too_short_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "title": "Fix bug"})
        assert result["passed"] is False
        assert any("short" in i.lower() for i in result["issues"])

    def test_missing_description_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "description": ""})
        assert result["passed"] is False
        assert any("description" in i.lower() for i in result["issues"])

    def test_description_too_short_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "description": "Crashes."})
        assert result["passed"] is False

    def test_missing_priority_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "priority": ""})
        assert result["passed"] is False
        assert any("priority" in i.lower() for i in result["issues"])

    def test_invalid_category_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "category": "Unknown"})
        assert result["passed"] is False
        assert any("category" in i.lower() for i in result["issues"])

    def test_invalid_priority_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "priority": "Urgent"})
        assert result["passed"] is False
        assert any("priority" in i.lower() for i in result["issues"])

    def test_bug_missing_technical_details_fails(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "technical_details": ""})
        assert result["passed"] is False
        assert any("technical_details" in i for i in result["issues"])

    def test_feature_without_technical_details_passes(self, agent):
        result = agent.review_locally({**COMPLETE_FEATURE, "technical_details": ""})
        assert result["passed"] is True

    def test_multiple_issues_all_reported(self, agent):
        result = agent.review_locally({
            "source_id": "R001", "source_type": "review",
            "title": "", "description": "", "category": "Bug",
            "priority": "", "technical_details": "",
        })
        assert result["passed"] is False
        assert len(result["issues"]) >= 3

    def test_none_field_treated_as_missing(self, agent):
        result = agent.review_locally({**COMPLETE_BUG, "title": None})
        assert result["passed"] is False


class TestReviewWithLLM:
    @pytest.mark.asyncio
    async def test_passes_on_llm_success(self):
        agent = QualityCriticAgent(model_client=MagicMock())
        msg = MagicMock()
        msg.content = json.dumps({"passed": True, "issues": []})
        result = MagicMock()
        result.messages = [msg]
        agent._agent.run = AsyncMock(return_value=result)
        out = await agent.review(COMPLETE_BUG)
        assert out.passed is True

    @pytest.mark.asyncio
    async def test_returns_issues_on_failure(self):
        agent = QualityCriticAgent(model_client=MagicMock())
        msg = MagicMock()
        msg.content = json.dumps({"passed": False, "issues": ["Title too generic"]})
        result = MagicMock()
        result.messages = [msg]
        agent._agent.run = AsyncMock(return_value=result)
        out = await agent.review(COMPLETE_BUG)
        assert out.passed is False
        assert "Title too generic" in out.issues

    @pytest.mark.asyncio
    async def test_falls_back_to_local_on_llm_error(self):
        agent = QualityCriticAgent(model_client=MagicMock())
        agent._agent.run = AsyncMock(side_effect=Exception("LLM error"))
        out = await agent.review(COMPLETE_BUG)
        assert out.passed is True  # complete bug passes local review

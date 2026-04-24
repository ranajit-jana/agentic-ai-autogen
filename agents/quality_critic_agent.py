import json
import re

from autogen_agentchat.agents import AssistantAgent
from pydantic import BaseModel

from agents.tracer import get_client
from config import MODEL_NAME, VALID_CATEGORIES, VALID_PRIORITIES

_REQUIRED_FIELDS = ["source_id", "source_type", "title", "description", "category", "priority"]
_MIN_TITLE_LEN = 10
_MIN_DESCRIPTION_LEN = 20

_SYSTEM = (
    "You are a meticulous engineering manager who reviews tickets before they enter the sprint. "
    "Reject vague, incomplete, or inaccurate tickets. Enforce high standards. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)


class QualityReviewOutput(BaseModel):
    passed: bool
    issues: list[str]


class QualityCriticAgent:
    def __init__(self, model_client=None):
        self._agent = (
            AssistantAgent(
                name="quality_critic",
                system_message=_SYSTEM,
                model_client=model_client,
            )
            if model_client
            else None
        )

    async def review(self, state: dict) -> QualityReviewOutput:
        if self._agent is None:
            return QualityReviewOutput(**self.review_locally(state))

        ticket_str = "\n".join(
            f"  {k}: {v}"
            for k, v in state.items()
            if k in (*_REQUIRED_FIELDS, "technical_details", "created_at")
        )
        prompt = f"""Review this engineering ticket for quality and completeness.

Ticket:
{ticket_str}

Evaluate against these criteria:
1. All required fields are present and non-empty: {_REQUIRED_FIELDS}
2. Title is at least {_MIN_TITLE_LEN} characters and is specific/actionable (not generic like "Fix bug")
3. Description is at least {_MIN_DESCRIPTION_LEN} characters with enough context for an engineer
4. Description has all three sections: Summary, Details, User Impact
5. Category is one of: {VALID_CATEGORIES}
6. Priority is one of: {VALID_PRIORITIES}
7. Bug tickets must have non-empty technical_details with platform/steps/severity info

Return ONLY a JSON object with "passed" (bool) and "issues" (list of strings, empty if passed)."""

        lf = get_client()
        try:
            with lf.start_as_current_observation(
                name="quality_critic",
                as_type="generation",
                model=MODEL_NAME,
                input=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
                metadata={"source_id": state.get("id"), "category": state.get("category")},
            ):
                result = await self._agent.run(task=prompt)
                raw = _last_text(result)
                lf.update_current_generation(output=raw)
            data = _parse_json(raw)
            return QualityReviewOutput(**data)
        except Exception:
            return QualityReviewOutput(**self.review_locally(state))

    def review_locally(self, state: dict) -> dict:
        issues = []
        for field in _REQUIRED_FIELDS:
            if not str(state.get(field, "")).strip():
                issues.append(f"Missing required field: '{field}'")

        title = str(state.get("title", "")).strip()
        if title and len(title) < _MIN_TITLE_LEN:
            issues.append(f"Title too short ({len(title)} chars, min {_MIN_TITLE_LEN})")

        description = str(state.get("description", "")).strip()
        if description and len(description) < _MIN_DESCRIPTION_LEN:
            issues.append(f"Description too short ({len(description)} chars, min {_MIN_DESCRIPTION_LEN})")

        category = state.get("category", "")
        if category and category not in VALID_CATEGORIES:
            issues.append(f"Invalid category: '{category}'")

        priority = state.get("priority", "")
        if priority and priority not in VALID_PRIORITIES:
            issues.append(f"Invalid priority: '{priority}'")

        if category == "Bug" and not str(state.get("technical_details", "")).strip():
            issues.append("Bug ticket is missing technical_details")

        return {"passed": len(issues) == 0, "issues": issues}


def _last_text(result) -> str:
    for msg in reversed(result.messages):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            return content
    return ""


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    m2 = re.search(r"\{[\s\S]*?\}", text)
    if m2:
        text = m2.group(0)
    return json.loads(text)

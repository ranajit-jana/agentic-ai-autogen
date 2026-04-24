import json
import re

from autogen_agentchat.agents import AssistantAgent
from pydantic import BaseModel, field_validator

from agents.tracer import get_client
from config import MODEL_NAME

_VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}

_SYSTEM = (
    "You are a senior QA engineer with deep expertise in mobile app debugging. "
    "Extract technical bug details from user reports, even when vague or incomplete. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)


class BugAnalysisOutput(BaseModel):
    platform: str
    os_version: str
    steps_to_reproduce: str
    severity: str

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        return v if v in _VALID_SEVERITIES else "Medium"


class BugAnalysisAgent:
    def __init__(self, model_client):
        self._agent = AssistantAgent(
            name="bug_analyst",
            system_message=_SYSTEM,
            model_client=model_client,
        )

    async def analyze(self, item: dict) -> BugAnalysisOutput:
        prompt = f"""Extract technical bug details from this user feedback.

Feedback:
{item['text']}

Extract:
- platform: Device/OS platform (e.g. "iOS 17.4", "Android 13"). Use "Unknown" if not mentioned.
- os_version: Specific OS version if mentioned, else "Unknown".
- steps_to_reproduce: Steps that trigger the bug. Use "Not specified" if absent.
- severity:
  * Critical: Data loss, complete app failure, blocks all users
  * High: Major feature broken (login/sync/export), affects many users
  * Medium: Feature broken but workaround exists, affects some users
  * Low: Minor annoyance or cosmetic issue

Return ONLY a JSON object with all four fields."""

        lf = get_client()
        with lf.start_as_current_observation(
            name="bug_analyst",
            as_type="generation",
            model=MODEL_NAME,
            input=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            metadata={"source_id": item.get("id"), "source_type": item.get("source_type")},
        ):
            result = await self._agent.run(task=prompt)
            raw = _last_text(result)
            lf.update_current_generation(output=raw)

        data = _parse_json(raw)
        return BugAnalysisOutput(**data)


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

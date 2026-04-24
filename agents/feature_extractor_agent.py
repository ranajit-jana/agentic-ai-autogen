import json
import re

from autogen_agentchat.agents import AssistantAgent
from pydantic import BaseModel, field_validator

from agents.tracer import get_client
from config import MODEL_NAME

_VALID_IMPACTS = {"High", "Medium", "Low"}

_SYSTEM = (
    "You are an experienced product analyst who has reviewed thousands of feature requests "
    "for mobile apps. You understand user needs deeply and assess impact and demand accurately. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)


class FeatureExtractionOutput(BaseModel):
    feature_description: str
    user_impact: str
    demand_score: int

    @field_validator("user_impact")
    @classmethod
    def validate_impact(cls, v: str) -> str:
        return v if v in _VALID_IMPACTS else "Medium"

    @field_validator("demand_score")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(1, min(10, int(v)))


class FeatureExtractorAgent:
    def __init__(self, model_client):
        self._agent = AssistantAgent(
            name="feature_analyst",
            system_message=_SYSTEM,
            model_client=model_client,
        )

    async def extract(self, item: dict) -> FeatureExtractionOutput:
        prompt = f"""Extract feature request details from this user feedback.

Feedback:
{item['text']}

Extract:
- feature_description: Clear, concise description of the requested feature (1–2 sentences, actionable).
- user_impact: How broadly this benefits users:
  * High: Affects core workflows, requested by many users, significantly improves daily use
  * Medium: Useful improvement, benefits a specific user segment
  * Low: Nice-to-have, niche use case, minor convenience
- demand_score: Integer 1–10 estimating user demand (1=very niche, 10=widely needed/urgent).

Return ONLY a JSON object with all three fields."""

        lf = get_client()
        with lf.start_as_current_observation(
            name="feature_analyst",
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
        return FeatureExtractionOutput(**data)


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

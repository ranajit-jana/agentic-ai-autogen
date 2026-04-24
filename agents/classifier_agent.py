import json
import re

from autogen_agentchat.agents import AssistantAgent
from pydantic import BaseModel, field_validator

from agents.tracer import get_client
from config import MODEL_NAME, VALID_CATEGORIES

_SYSTEM = (
    "You are an expert content analyst specializing in mobile app user feedback. "
    "Classify feedback into exactly one of 5 categories with a confidence score. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)


class ClassificationOutput(BaseModel):
    category: str
    confidence: float

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        return v if v in VALID_CATEGORIES else "Complaint"

    @field_validator("confidence")
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class ClassifierAgent:
    def __init__(self, model_client):
        self._agent = AssistantAgent(
            name="classifier",
            system_message=_SYSTEM,
            model_client=model_client,
        )

    async def classify(self, item: dict) -> ClassificationOutput:
        prompt = f"""Classify this user feedback for a B2C mobile productivity app.

Categories (choose exactly one):
- Bug: Technical problem, crash, error, or broken functionality
- Feature Request: Request for new functionality or improvements
- Praise: Positive sentiment or satisfaction
- Complaint: Dissatisfaction about pricing, support, or performance (NOT a technical bug)
- Spam: Promotional, random, unrelated, or meaningless content

Source: {item['source_type']} (ID: {item['id']})
Feedback:
{item['text']}

Return ONLY a JSON object with "category" and "confidence" (float 0.0–1.0)."""

        lf = get_client()
        with lf.start_as_current_observation(
            name="classifier",
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
        return ClassificationOutput(**data)


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

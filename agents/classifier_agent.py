import json
import re

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, field_validator

from agents.tracer import get_client
from config import MODEL_NAME, VALID_CATEGORIES

_SYSTEM = (
    "You are an expert content analyst specializing in mobile app user feedback. "
    "Classify feedback into exactly one of 5 categories with a confidence score. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)

# Fresh session per call keeps each LLM interaction stateless
_APP_NAME = "feedback_pipeline"


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
    def __init__(self, model: str = MODEL_NAME):
        self._agent = Agent(
            name="classifier",
            model=LiteLlm(model=model),
            instruction=_SYSTEM,
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
            raw = await _invoke_agent(self._agent, prompt)
            lf.update_current_generation(output=raw)

        data = _parse_json(raw)
        return ClassificationOutput(**data)


async def _invoke_agent(agent: Agent, prompt: str) -> str:
    import asyncio as _asyncio
    # Each call gets its own session — no accumulated history across items
    for attempt in range(4):
        try:
            session_service = InMemorySessionService()
            session = await session_service.create_session(app_name=_APP_NAME, user_id="pipeline")
            runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)
            content = types.Content(role="user", parts=[types.Part(text=prompt)])
            text = ""
            async for event in runner.run_async(
                user_id="pipeline", session_id=session.id, new_message=content
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            text += part.text
            return text
        except Exception as exc:
            if "rate_limit" in str(exc).lower() and attempt < 3:
                await _asyncio.sleep(10 * (2 ** attempt))
            else:
                raise


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    m2 = re.search(r"\{[\s\S]*?\}", text)
    if m2:
        text = m2.group(0)
    return json.loads(text)

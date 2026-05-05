import json
import re

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, field_validator

from agents.tracer import get_client
from config import MODEL_NAME

_VALID_IMPACTS = {"High", "Medium", "Low"}

_SYSTEM = (
    "You are an experienced product analyst who has reviewed thousands of feature requests "
    "for mobile apps. You understand user needs deeply and assess impact and demand accurately. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)

# Fresh session per call keeps each LLM interaction stateless
_APP_NAME = "feedback_pipeline"


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
    def __init__(self, model: str = MODEL_NAME):
        self._agent = Agent(
            name="feature_analyst",
            model=LiteLlm(model=model),
            instruction=_SYSTEM,
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
            raw = await _invoke_agent(self._agent, prompt)
            lf.update_current_generation(output=raw)

        data = _parse_json(raw)
        return FeatureExtractionOutput(**data)


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

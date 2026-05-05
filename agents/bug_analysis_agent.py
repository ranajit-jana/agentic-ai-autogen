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

_VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}

_SYSTEM = (
    "You are a senior QA engineer with deep expertise in mobile app debugging. "
    "Extract technical bug details from user reports, even when vague or incomplete. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)

# Fresh session per call keeps each LLM interaction stateless
_APP_NAME = "feedback_pipeline"


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
    def __init__(self, model: str = MODEL_NAME):
        self._agent = Agent(
            name="bug_analyst",
            model=LiteLlm(model=model),
            instruction=_SYSTEM,
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
            raw = await _invoke_agent(self._agent, prompt)
            lf.update_current_generation(output=raw)

        data = _parse_json(raw)
        return BugAnalysisOutput(**data)


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

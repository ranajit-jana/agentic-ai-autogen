import csv
import json
import os
import re
from datetime import datetime, timezone

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from agents.tracer import get_client
from config import DEFAULT_PRIORITY, MODEL_NAME, TICKETS_FILE, VALID_PRIORITIES

_TICKET_COLUMNS = [
    "ticket_id", "source_id", "source_type", "title", "description",
    "category", "priority", "technical_details", "created_at",
]

_COUNTER_FILE = "data/output/.ticket_counter"

_SYSTEM = (
    "You are an expert technical writer with years of experience creating engineering tickets "
    "for mobile app teams. Distill user feedback into concise, well-structured tickets. "
    "Respond ONLY with a valid JSON object — no prose, no markdown fences."
)

# Fresh session per call keeps each LLM interaction stateless
_APP_NAME = "feedback_pipeline"


class TicketOutput(BaseModel):
    title: str
    description: str


class TicketCreatorAgent:
    def __init__(self, model: str = MODEL_NAME):
        self._agent = Agent(
            name="ticket_creator",
            model=LiteLlm(model=model),
            instruction=_SYSTEM,
        )

    async def create(self, state: dict) -> dict:
        context_str = _build_context_str(state)
        retry_hint = ""
        if state.get("retry_count", 0) > 0 and state.get("quality_issues"):
            issues = "\n".join(f"  - {i}" for i in state["quality_issues"])
            retry_hint = f"\n\nPREVIOUS ATTEMPT FAILED quality review. Fix these issues:\n{issues}"

        prompt = f"""Create an engineering ticket from this enriched feedback.

{context_str}{retry_hint}

Generate:
- title: Concise, actionable title (max 80 chars). Start with Fix, Add, Investigate, or Improve.
- description: Structured ticket body using exactly this format:
  **Summary:** One sentence describing the issue or request.
  **Details:** Key technical details, steps to reproduce, or context.
  **User Impact:** How this affects users and why it matters.

Return ONLY a JSON object with "title" and "description"."""

        lf = get_client()
        with lf.start_as_current_observation(
            name="ticket_creator",
            as_type="generation",
            model=MODEL_NAME,
            input=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            metadata={
                "source_id": state.get("id"),
                "category": state.get("category"),
                "retry_count": state.get("retry_count", 0),
            },
        ):
            raw = await _invoke_agent(self._agent, prompt)
            lf.update_current_generation(output=raw)

        data = _parse_json(raw)
        output = TicketOutput(**data)

        return {
            "source_id": state.get("id"),
            "source_type": state.get("source_type"),
            "title": output.title[:80],
            "description": output.description,
            "priority": _derive_priority(state),
            "technical_details": _build_technical_details(state),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# CSV utilities
# ---------------------------------------------------------------------------

def ensure_csv() -> None:
    os.makedirs("data/output", exist_ok=True)
    if not os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=_TICKET_COLUMNS).writeheader()


def append_to_csv(ticket: dict) -> None:
    with open(TICKETS_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_TICKET_COLUMNS).writerow(ticket)


def next_ticket_id() -> str:
    os.makedirs("data/output", exist_ok=True)
    try:
        with open(_COUNTER_FILE) as f:
            n = int(f.read().strip()) + 1
    except (FileNotFoundError, ValueError):
        n = 1
    with open(_COUNTER_FILE, "w") as f:
        f.write(str(n))
    return f"T{n:04d}"


def build_ticket_from_state(state: dict) -> dict:
    return {
        "ticket_id": next_ticket_id(),
        "source_id": state["id"],
        "source_type": state["source_type"],
        "title": state.get("title", ""),
        "description": state.get("description", ""),
        "category": state.get("category", ""),
        "priority": state.get("priority", ""),
        "technical_details": state.get("technical_details", ""),
        "created_at": state.get("created_at", ""),
    }


# ---------------------------------------------------------------------------
# ADK runner
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_priority(state: dict) -> str:
    category = state.get("category", "Complaint")
    if category == "Bug":
        severity = state.get("severity", "")
        return severity if severity in VALID_PRIORITIES else DEFAULT_PRIORITY["Bug"]
    if category == "Feature Request":
        score = state.get("demand_score", 5)
        if score >= 8:
            return "High"
        if score >= 5:
            return "Medium"
        return "Low"
    return DEFAULT_PRIORITY.get(category, "Low")


def _build_technical_details(state: dict) -> str:
    parts = []
    category = state.get("category", "")
    if category == "Bug":
        if state.get("platform") and state["platform"] != "Unknown":
            parts.append(f"Platform: {state['platform']}")
        if state.get("os_version") and state["os_version"] != "Unknown":
            parts.append(f"OS: {state['os_version']}")
        if state.get("steps_to_reproduce") and state["steps_to_reproduce"] != "Not specified":
            parts.append(f"Steps: {state['steps_to_reproduce']}")
        if state.get("severity"):
            parts.append(f"Severity: {state['severity']}")
    elif category == "Feature Request":
        if state.get("user_impact"):
            parts.append(f"User Impact: {state['user_impact']}")
        if state.get("demand_score"):
            parts.append(f"Demand Score: {state['demand_score']}/10")
        if state.get("feature_description"):
            parts.append(f"Feature: {state['feature_description']}")
    return " | ".join(parts) if parts else ""


def _build_context_str(state: dict) -> str:
    lines = [
        f"Category: {state.get('category', 'Unknown')}",
        f"Source: {state['source_type']} (ID: {state['id']})",
        f"Original feedback:\n{state['text']}",
    ]
    if state.get("severity"):
        lines.append(f"Bug severity: {state['severity']}")
    if state.get("platform") and state["platform"] != "Unknown":
        lines.append(f"Platform: {state['platform']}")
    if state.get("steps_to_reproduce") and state["steps_to_reproduce"] != "Not specified":
        lines.append(f"Steps to reproduce: {state['steps_to_reproduce']}")
    if state.get("feature_description"):
        lines.append(f"Feature description: {state['feature_description']}")
    if state.get("user_impact"):
        lines.append(f"User impact: {state['user_impact']}")
    if state.get("demand_score"):
        lines.append(f"Demand score: {state['demand_score']}/10")
    return "\n".join(lines)


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    m2 = re.search(r"\{[\s\S]*?\}", text)
    if m2:
        text = m2.group(0)
    return json.loads(text)

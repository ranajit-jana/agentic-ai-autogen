import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from typing import Callable

from autogen_ext.models.anthropic import AnthropicChatCompletionClient

import agents.classifier_agent as classifier_mod
import agents.bug_analysis_agent as bug_mod
import agents.feature_extractor_agent as feature_mod
import agents.ticket_creator_agent as ticket_mod
import agents.quality_critic_agent as quality_mod
from agents.csv_reader_agent import CSVReaderAgent
from agents.tracer import get_client
from config import ANTHROPIC_API_KEY, CONFIDENCE_THRESHOLD, MODEL_NAME
from logger import PipelineLogger

END = "__end__"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class FeedbackGraph:
    """Directed graph with conditional routing ."""

    def __init__(self):
        self._nodes: dict[str, Callable] = {}
        self._edges: dict[str, str] = {}
        self._conditional: dict[str, tuple[Callable, dict]] = {}
        self._entry: str | None = None

    def add_node(self, name: str, fn: Callable) -> "FeedbackGraph":
        self._nodes[name] = fn
        return self

    def add_edge(self, src: str, dst: str) -> "FeedbackGraph":
        self._edges[src] = dst
        return self

    def add_conditional_edges(
        self, src: str, router: Callable, mapping: dict
    ) -> "FeedbackGraph":
        self._conditional[src] = (router, mapping)
        return self

    def set_entry_point(self, name: str) -> "FeedbackGraph":
        self._entry = name
        return self

    async def invoke(self, state: dict) -> dict:
        current = self._entry
        while current and current != END:
            updates = await self._nodes[current](state)
            state.update(updates)
            if current in self._conditional:
                router, mapping = self._conditional[current]
                current = mapping.get(router(state), END)
            else:
                current = self._edges.get(current, END)
        return state


# ---------------------------------------------------------------------------
# Agent factory + graph builder
# ---------------------------------------------------------------------------

def _make_model_client() -> AnthropicChatCompletionClient:
    return AnthropicChatCompletionClient(
        model=MODEL_NAME,
        api_key=ANTHROPIC_API_KEY,
    )


def _build_agents(model_client) -> dict:
    return {
        "classifier": classifier_mod.ClassifierAgent(model_client),
        "bug_analyst": bug_mod.BugAnalysisAgent(model_client),
        "feature_analyst": feature_mod.FeatureExtractorAgent(model_client),
        "ticket_creator": ticket_mod.TicketCreatorAgent(model_client),
        "quality_critic": quality_mod.QualityCriticAgent(model_client),
    }


def _build_graph(agents: dict) -> FeedbackGraph:
    graph = FeedbackGraph()

    # ── Nodes ────────────────────────────────────────────────────────────────

    async def classify_node(state: dict) -> dict:
        out = await agents["classifier"].classify(state)
        return {"category": out.category, "confidence": out.confidence}

    async def bug_node(state: dict) -> dict:
        out = await agents["bug_analyst"].analyze(state)
        return out.model_dump()

    async def feature_node(state: dict) -> dict:
        out = await agents["feature_analyst"].extract(state)
        return out.model_dump()

    async def ticket_node(state: dict) -> dict:
        return await agents["ticket_creator"].create(state)

    async def quality_node(state: dict) -> dict:
        out = await agents["quality_critic"].review(state)
        updates: dict = {"quality_passed": out.passed, "quality_issues": out.issues}
        if not out.passed:
            updates["retry_count"] = state.get("retry_count", 0) + 1
        return updates

    graph.add_node("classifier", classify_node)
    graph.add_node("bug_analyzer", bug_node)
    graph.add_node("feature_extractor", feature_node)
    graph.add_node("ticket_creator", ticket_node)
    graph.add_node("quality_critic", quality_node)

    # ── Edges ─────────────────────────────────────────────────────────────────

    graph.set_entry_point("classifier")

    def route_after_classify(state: dict) -> str:
        if state.get("confidence", 0) < CONFIDENCE_THRESHOLD:
            return "low_confidence"
        return state.get("category", "Spam")

    graph.add_conditional_edges("classifier", route_after_classify, {
        "Bug":             "bug_analyzer",
        "Feature Request": "feature_extractor",
        "Praise":          END,
        "Complaint":       END,
        "Spam":            END,
        "low_confidence":  END,
    })

    graph.add_edge("bug_analyzer", "ticket_creator")
    graph.add_edge("feature_extractor", "ticket_creator")
    graph.add_edge("ticket_creator", "quality_critic")

    def route_after_quality(state: dict) -> str:
        if state.get("quality_passed"):
            return "passed"
        if state.get("retry_count", 0) <= 1:
            return "retry"
        return "failed"

    graph.add_conditional_edges("quality_critic", route_after_quality, {
        "passed": END,
        "retry":  "ticket_creator",
        "failed": END,
    })

    return graph


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

async def _run_pipeline(run_id: str, log: "PipelineLogger", limit: int | None) -> dict:
    model_client = _make_model_client()
    ticket_mod.ensure_csv()

    items = CSVReaderAgent().read_all()
    if limit:
        items = items[:limit]

    total = len(items)
    counts = {"created": 0, "skipped": 0, "failed": 0}
    category_counts: dict[str, int] = {}

    print(f"\n[{run_id}] Processing {total} feedback item(s) via AutoGen graph...\n")

    for item in items:
        source_id = item["id"]
        source_type = item["source_type"]

        # Fresh agents per item — avoids accumulated conversation context
        agents = _build_agents(model_client)
        graph = _build_graph(agents)
        state: dict = {**item, "retry_count": 0, "quality_passed": False}

        lf = get_client()
        try:
            with lf.start_as_current_observation(
                name="feedback-item",
                as_type="agent",
                input={"id": source_id, "source_type": source_type, "text": item["text"][:500]},
                metadata={"run_id": run_id},
            ) as obs:
                state = await graph.invoke(state)
                obs.update(
                    output={
                        "category": state.get("category"),
                        "confidence": state.get("confidence"),
                        "ticket_created": bool(state.get("quality_passed")),
                    },
                )
        except Exception as exc:
            print(f"  [{source_id}] ERROR — {exc}")
            log.log_step(source_id, source_type, "pipeline", "error")
            counts["failed"] += 1
            continue

        category = state.get("category", "Unknown")
        confidence = state.get("confidence", 0.0)
        category_counts[category] = category_counts.get(category, 0) + 1

        log.log_step(
            source_id, source_type, "classifier", category,
            confidence=confidence,
            input_data={"text": item["text"][:200]},
            output_data={"category": category, "confidence": confidence},
        )

        # Items that hit END before ticket creation
        if category in ("Praise", "Complaint", "Spam"):
            reason = category.lower()
            print(f"  [{source_id}] SKIPPED — {reason}")
            counts["skipped"] += 1
            continue
        if confidence < CONFIDENCE_THRESHOLD:
            reason = f"low-confidence ({confidence:.2f})"
            print(f"  [{source_id}] SKIPPED — {reason}")
            log.log_step(source_id, source_type, "filter", "skipped",
                         output_data={"reason": reason})
            counts["skipped"] += 1
            continue

        if state.get("quality_passed"):
            ticket = ticket_mod.build_ticket_from_state(state)
            ticket_mod.append_to_csv(ticket)
            tid = ticket["ticket_id"]
            title = ticket["title"][:55]
            print(f"  [{source_id}] OK  — {category:<18} → {tid}: {title}")
            log.log_step(source_id, source_type, "ticket_creator", "created",
                         output_data={"ticket_id": tid, "title": ticket["title"]})
            counts["created"] += 1
        else:
            issues = state.get("quality_issues", [])
            print(f"  [{source_id}] FAIL — quality check failed: {', '.join(issues)}")
            log.log_step(source_id, source_type, "quality_critic", "failed",
                         output_data={"issues": issues})
            counts["failed"] += 1

    stats = {"total": total, **counts, "category_counts": category_counts}
    log.log_metrics(stats)

    divider = "=" * 60
    print(f"\n{divider}")
    print(f"  Run ID           : {run_id}")
    print(f"  Total items      : {total}")
    print(f"  Tickets created  : {counts['created']}")
    print(f"  Skipped          : {counts['skipped']}")
    print(f"  Failed / Errored : {counts['failed']}")
    print(f"\n  Category breakdown:")
    for cat in sorted(category_counts):
        print(f"    {cat:<22} {category_counts[cat]}")
    print(divider)

    return stats


def run(limit: int | None = None) -> dict:
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    with PipelineLogger(run_id=run_id) as log:
        return asyncio.run(_run_pipeline(run_id, log, limit))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the feedback pipeline via AutoGen graph.")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Process only the first N items.")
    args = parser.parse_args()
    result = run(limit=args.limit)
    sys.exit(0 if result["failed"] == 0 else 1)

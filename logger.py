import csv
import os
from datetime import datetime, timezone
from types import TracebackType

from config import LOG_FILE, METRICS_FILE

_LOG_COLUMNS = ["source_id", "source_type", "agent", "decision", "confidence", "timestamp"]
_METRICS_COLUMNS = [
    "run_id", "run_at", "total_processed", "tickets_created", "skipped", "failed",
    "bug_count", "feature_request_count", "praise_count", "complaint_count", "spam_count",
]


def _ensure_csv(path: str, columns: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=columns).writeheader()


class PipelineLogger:
    """
    Simple CSV logger:
      - Appends per-step rows to processing_log.csv
      - Appends run-level metrics to metrics.csv
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        _ensure_csv(LOG_FILE, _LOG_COLUMNS)
        _ensure_csv(METRICS_FILE, _METRICS_COLUMNS)

    # ------------------------------------------------------------------
    # Context manager (kept for structure, no-op)
    # ------------------------------------------------------------------

    def __enter__(self) -> "PipelineLogger":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    # ------------------------------------------------------------------
    # Per-item logging
    # ------------------------------------------------------------------

    def log_step(
        self,
        source_id: str,
        source_type: str,
        agent: str,
        decision: str,
        confidence: float | None = None,
        input_data: dict | None = None,
        output_data: dict | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        with open(LOG_FILE, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=_LOG_COLUMNS).writerow({
                "source_id": source_id,
                "source_type": source_type,
                "agent": agent,
                "decision": decision,
                "confidence": confidence if confidence is not None else "",
                "timestamp": now,
            })

    # ------------------------------------------------------------------
    # Run-level metrics
    # ------------------------------------------------------------------

    def log_metrics(self, stats: dict) -> None:
        row = {
            "run_id": self.run_id,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "total_processed": stats.get("total", 0),
            "tickets_created": stats.get("created", 0),
            "skipped": stats.get("skipped", 0),
            "failed": stats.get("failed", 0),
            "bug_count": stats.get("category_counts", {}).get("Bug", 0),
            "feature_request_count": stats.get("category_counts", {}).get("Feature Request", 0),
            "praise_count": stats.get("category_counts", {}).get("Praise", 0),
            "complaint_count": stats.get("category_counts", {}).get("Complaint", 0),
            "spam_count": stats.get("category_counts", {}).get("Spam", 0),
        }

        with open(METRICS_FILE, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=_METRICS_COLUMNS).writerow(row)
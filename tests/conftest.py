from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_langfuse(monkeypatch):
    """Prevent any agent from hitting Langfuse during tests."""
    lf = MagicMock()

    @contextmanager
    def _fake_observation(**kwargs):
        yield MagicMock()

    lf.start_as_current_observation = _fake_observation
    lf.update_current_generation = MagicMock()
    lf.set_current_trace_io = MagicMock()

    stub = lambda: lf  # noqa: E731
    for mod in [
        "agents.classifier_agent",
        "agents.bug_analysis_agent",
        "agents.feature_extractor_agent",
        "agents.ticket_creator_agent",
        "agents.quality_critic_agent",
        "pipeline",
    ]:
        monkeypatch.setattr(f"{mod}.get_client", stub)

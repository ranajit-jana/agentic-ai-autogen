import os
from contextlib import contextmanager

from langfuse import Langfuse


class _NoOpSpan:
    def update(self, **kwargs): pass


class _NoOpLangfuse:
    @contextmanager
    def start_as_current_observation(self, **kwargs):
        yield _NoOpSpan()

    def update_current_generation(self, **kwargs): pass
    def set_current_trace_io(self, **kwargs): pass


_client = None


def get_client():
    global _client
    if _client is None:
        if os.getenv("LANGFUSE_ENABLED", "true").lower() == "false":
            _client = _NoOpLangfuse()
        else:
            _client = Langfuse()
    return _client

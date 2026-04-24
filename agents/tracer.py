from langfuse import Langfuse

_client: Langfuse | None = None


def get_client() -> Langfuse:
    global _client
    if _client is None:
        _client = Langfuse()
    return _client

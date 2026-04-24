"""Chat stream client credential refresh tests."""

from app.services import chat_stream


def test_get_client_rebuilds_when_key_fingerprint_changes(monkeypatch) -> None:
    chat_stream.reset_client()
    api_keys: list[str] = []

    class _FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            api_keys.append(api_key)

    monkeypatch.setattr(chat_stream.genai, "Client", _FakeClient)
    monkeypatch.setattr(
        chat_stream,
        "_resolve_api_key_from_sources",
        lambda: ("key-v1", "fp-v1", "database"),
    )

    first_client = chat_stream.get_client()
    second_client = chat_stream.get_client()
    assert first_client is second_client
    assert api_keys == ["key-v1"]

    monkeypatch.setattr(
        chat_stream,
        "_resolve_api_key_from_sources",
        lambda: ("key-v2", "fp-v2", "database"),
    )
    refreshed_client = chat_stream.get_client()
    assert refreshed_client is not first_client
    assert api_keys == ["key-v1", "key-v2"]

    chat_stream.reset_client()

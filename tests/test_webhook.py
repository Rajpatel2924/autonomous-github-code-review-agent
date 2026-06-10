import hashlib
import hmac

from app.webhook import is_supported_pull_request_event, valid_signature


def test_valid_signature() -> None:
    body = b'{"action":"opened"}'
    secret = "webhook-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert valid_signature(body, signature, secret)
    assert not valid_signature(body, "sha256=wrong", secret)
    assert not valid_signature(body, None, secret)


def test_pull_request_event_filter() -> None:
    assert is_supported_pull_request_event("pull_request", {"action": "opened"})
    assert is_supported_pull_request_event("pull_request", {"action": "synchronize"})
    assert not is_supported_pull_request_event("push", {"action": "opened"})
    assert not is_supported_pull_request_event("pull_request", {"action": "closed"})

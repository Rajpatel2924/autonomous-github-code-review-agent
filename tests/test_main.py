import hashlib
import hmac

from app.main import valid_signature


def test_valid_signature() -> None:
    body = b'{"action":"opened"}'
    secret = "webhook-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert valid_signature(body, signature, secret)
    assert not valid_signature(body, "sha256=wrong", secret)
    assert not valid_signature(body, None, secret)

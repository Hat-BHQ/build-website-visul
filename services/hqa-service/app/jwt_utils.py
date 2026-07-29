import base64
import hashlib
import hmac
import json
import time


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encode_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64encode(json.dumps(header, separators=(',', ':')).encode())}.{_b64encode(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def decode_jwt(token: str, secret: str) -> dict:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual = _b64decode(signature_part)
        if not hmac.compare_digest(expected, actual):
            raise ValueError("Invalid signature")
        payload = json.loads(_b64decode(payload_part))
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("Token expired")
        return payload
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid access token") from exc

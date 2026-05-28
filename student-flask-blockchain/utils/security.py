import hashlib


def sha256_hex(text: str) -> str:
    if text is None:
        text = ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest


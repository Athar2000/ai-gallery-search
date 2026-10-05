import hashlib


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

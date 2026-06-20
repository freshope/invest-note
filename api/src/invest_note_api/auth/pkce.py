"""PKCE S256 단일 출처(F8).

S256 challenge = urlsafe_b64(sha256(verifier)).rstrip('=') — Layer1(BE↔IdP)·Layer2(앱↔BE)
양쪽이 동일 정의를 써야 한다. 과거 oauth_providers._pkce_challenge ↔ routers/auth._pkce_verify
가 copy-paste 라 정의 비대칭(rstrip 누락 등) 위험이 있어 한 곳으로 모은다.
"""
from __future__ import annotations

import base64
import hashlib


def pkce_s256(verifier: str) -> str:
    """verifier → S256 code_challenge."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_s256(challenge: str, verifier: str) -> bool:
    """S256(verifier) == challenge 대조."""
    return pkce_s256(verifier) == challenge

"""인증 공통 상수."""

# OIDC JWT 검증용 기본값 — aud 클레임 값과 허용 서명 알고리즘.
# _verify_with_entry 가 entry.audience 빈 값일 때의 폴백 기본값으로 쓴다.
AUTH_ROLE = "authenticated"
JWT_ALGORITHMS = ["ES256", "RS256"]

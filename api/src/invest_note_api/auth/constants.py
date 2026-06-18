"""인증 공통 상수."""

# Supabase Auth JWT 검증용 — aud 클레임 값과 허용 서명 알고리즘 (Auth 축은 유지).
AUTH_ROLE = "authenticated"
JWT_ALGORITHMS = ["ES256", "RS256"]

"""인증 공통 상수."""

# OIDC JWT 검증용 기본값(현재 IdP=Supabase) — aud 클레임 값과 허용 서명 알고리즘.
# config 의 oidc_audience 기본값으로 쓰여 IdP 교체 시 한 곳만 갈아끼우면 된다.
AUTH_ROLE = "authenticated"
JWT_ALGORITHMS = ["ES256", "RS256"]

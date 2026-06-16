"""인증 공통 상수."""

# Supabase Auth JWT 검증용 — aud 클레임 값과 허용 서명 알고리즘 (Auth 축은 유지).
AUTH_ROLE = "authenticated"
JWT_ALGORITHMS = ["ES256", "RS256"]

# DB RLS 컨텍스트 — 표준 PostgreSQL 객체(Supabase 고유 객체 비의존).
DB_APP_ROLE = "app_authenticated"  # RLS 적용 역할 (Supabase 'authenticated' 대체)
DB_GUC_USER_ID = "app.current_user_id"  # public.current_user_id() 가 읽는 GUC

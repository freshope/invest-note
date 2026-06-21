-- Supabase auth.* → 백필 export SQL (cutover step 2: 최종 백필 입력 생성)
--
-- 산출물 2개:
--   identities.csv  → scripts/import_auth_identities.py  (provider, provider_id, user_id)
--   users.csv       → scripts/import_user_profiles.py     (user_id, email, display_name, avatar_url, email_verified, providers, last_sign_in_at)
--
-- 실행 방법(둘 중 하나):
--   A) Supabase Dashboard → SQL Editor 에 각 쿼리 붙여넣고 실행 → 결과 우측 "Download CSV".
--   B) psql 직접 접속(서비스 롤):  아래 \copy 변형 사용.
--
-- ⚠️ 실행 시점: 반드시 "Supabase 신규가입 동결(freeze)" **이후**. 동결 전 export 는 스냅샷이
--    불완전해 동결~export 사이 신규가입자가 매핑 없이 남아 cutover 후 고아화된다(gapless 깨짐).
--
-- ⚠️ 범위(중요): 백필 대상은 "앱을 실제 사용해 public.users 행이 있는 유저"뿐이다.
--    - import_auth_identities: public.users ⊆ export(coverage) 검증 + INSERT 가 user_id FK→public.users.
--      → export 에 public.users 에 없는 user_id 가 섞이면 --commit 시 FK 위반(주의: dry-run 은 INSERT
--        를 건너뛰어 이걸 못 잡음).
--    - import_user_profiles: export ⊆ public.users(anti-orphan) 검증 → 섞이면 dry-run 이 abort 로 보고.
--    Supabase 에는 public.users(앱 DB)가 없으므로 여기선 전체를 뽑되, **profiles dry-run 이 orphan 을
--    보고하면 그 user_id 들을 양쪽 CSV 에서 제외**하고 재시도한다(아래 [필터] 절 참고).


-- ════════════════════════════════════════════════════════════════════════════
-- [1] identities.csv  — auth.identities → auth_identities 매핑
-- ════════════════════════════════════════════════════════════════════════════
-- provider 는 importer 가 소문자 정규화한다. provider_id 는 Supabase auth.identities 의
-- NOT NULL 컬럼(=IdP sub). 비어 있는 변형 대비로 identity_data->>'sub' 폴백도 함께 둔다.
SELECT
    provider,
    COALESCE(NULLIF(provider_id, ''), identity_data->>'sub') AS provider_id,
    user_id
FROM auth.identities
ORDER BY user_id;

-- psql \copy 변형:
-- \copy (SELECT provider, COALESCE(NULLIF(provider_id,''), identity_data->>'sub') AS provider_id, user_id FROM auth.identities ORDER BY user_id) TO 'identities.csv' WITH (FORMAT csv, HEADER true)


-- ════════════════════════════════════════════════════════════════════════════
-- [2] users.csv  — auth.users → user_profiles 백필
-- ════════════════════════════════════════════════════════════════════════════
-- display_name: full_name → name 순 폴백. avatar_url: avatar_url → picture 폴백.
-- email_verified: email_confirmed_at 존재 여부(t/f, importer 가 't'/'true' 모두 인식).
-- providers: raw_app_meta_data.providers 배열을 콤마 결합(없으면 단일 provider 폴백).
-- last_sign_in_at: ISO-8601(Z) 로 출력 → importer 가 fromisoformat 으로 파싱(null 허용).
SELECT
    u.id AS user_id,
    u.email,
    COALESCE(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name')   AS display_name,
    COALESCE(u.raw_user_meta_data->>'avatar_url', u.raw_user_meta_data->>'picture') AS avatar_url,
    (u.email_confirmed_at IS NOT NULL)                                            AS email_verified,
    COALESCE(
        (SELECT string_agg(p, ',') FROM jsonb_array_elements_text(u.raw_app_meta_data->'providers') AS p),
        u.raw_app_meta_data->>'provider'
    )                                                                             AS providers,
    to_char(u.last_sign_in_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')   AS last_sign_in_at
FROM auth.users u
ORDER BY u.id;

-- psql \copy 변형:
-- \copy (SELECT u.id AS user_id, u.email, COALESCE(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name') AS display_name, COALESCE(u.raw_user_meta_data->>'avatar_url', u.raw_user_meta_data->>'picture') AS avatar_url, (u.email_confirmed_at IS NOT NULL) AS email_verified, COALESCE((SELECT string_agg(p, ',') FROM jsonb_array_elements_text(u.raw_app_meta_data->'providers') AS p), u.raw_app_meta_data->>'provider') AS providers, to_char(u.last_sign_in_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS last_sign_in_at FROM auth.users u ORDER BY u.id) TO 'users.csv' WITH (FORMAT csv, HEADER true)


-- ════════════════════════════════════════════════════════════════════════════
-- [참고] 카운트 정합 사전 확인 (export 직후, dry-run 전)
-- ════════════════════════════════════════════════════════════════════════════
-- auth.users 수 > public.users(앱 DB) 수 이면 "앱 미프로비저닝" 유저가 존재 → 위 [필터] 필요.
-- (public.users 는 앱 DB 에서: SELECT count(*) FROM public.users; 로 별도 확인)
SELECT
    (SELECT count(*) FROM auth.users)                          AS auth_users,
    (SELECT count(*) FROM auth.identities)                     AS auth_identities,
    (SELECT count(DISTINCT user_id) FROM auth.identities)      AS distinct_identity_users;


-- ════════════════════════════════════════════════════════════════════════════
-- [필터] profiles dry-run 이 orphan 을 보고할 때만 사용
-- ════════════════════════════════════════════════════════════════════════════
-- 1) 앱 DB 에서 유효 user_id 목록을 받는다:
--      psql(앱DB)>  \copy (SELECT id FROM public.users ORDER BY id) TO 'app_user_ids.csv' WITH (FORMAT csv, HEADER true)
-- 2) Supabase SQL Editor 에 app_user_ids 를 임시로 올리거나, 위 [1]·[2] 쿼리에
--    `WHERE u.id = ANY(ARRAY['uuid1','uuid2', ...]::uuid[])` (또는 identities 는 user_id)
--    형태로 허용목록을 끼워 재추출한다. 두 CSV 모두 같은 허용목록으로 한정해야 정합이 맞는다.

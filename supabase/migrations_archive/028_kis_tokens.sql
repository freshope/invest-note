-- KIS Open API 접근토큰 영속 저장소 — 1일 1토큰 정책 대응.
--
-- 토큰은 in-process 캐시(KisState)가 1차이고, 이 테이블은 프로세스 간 공유 + 재시작
-- 내구성을 위한 source of truth. 발급(1분 1회 제한, EGW00133)은 호출측에서
-- pg_advisory_xact_lock 으로 직렬화하고 같은 트랜잭션에서 upsert 한다.
--
-- 주의: stocks/daily_close_prices 의 "전역 참조 데이터 RLS 미적용" 패턴과 다르다.
-- 이 테이블은 서버 전용 비밀이므로 RLS 를 켜되 정책을 만들지 않는다
-- → anon/authenticated(PostgREST) 전면 차단, BE 는 owner(postgres) 접속이라 RLS 미적용.

create table public.kis_tokens (
    scope        text primary key,                  -- 'app' (추후 사용자 토큰은 'user:{id}' 확장).
    access_token text not null,
    expires_at   timestamptz not null,              -- KIS expires_in 기반 만료 시각.
    issued_at    timestamptz not null default now()
);

alter table public.kis_tokens enable row level security;

comment on table public.kis_tokens is
    'KIS 접근토큰 영속 저장소 (서버 전용 비밀). RLS enable + 정책 없음 = PostgREST 차단, BE(owner)만 접근.';

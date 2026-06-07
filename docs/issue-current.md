# Spec: KIS 토큰 DB 영속화 (1일 1토큰 정책 대응)

## 배경 / 문제

KIS Open API 접근토큰은 "1일 1회 발급" 원칙(유효 24h, 갱신주기 6h, 발급 1분 1회 제한 — EGW00133)이 있다.
현재 토큰은 `KisState` 모듈 싱글톤의 프로세스 메모리에만 캐시되어, 재배포/재시작마다 발급 호출이 발생하고,
멀티 프로세스(롤링 배포 중 신·구 컨테이너 동시 실행, 추후 멀티워커) 시 토큰이 어긋날 수 있다.
조사 결과(Redis vs DB) 기존 PostgreSQL(Supabase)에 영속화하기로 결정 — 저빈도(하루 1~4회 쓰기)·고내구성
요구라 Redis 도입은 불필요하다.

## 목표

- 토큰이 DB(`kis_tokens` 테이블)에 영속화되어 앱 재시작 후에도 발급 호출 없이 재사용된다.
- 동시 발급이 `pg_advisory_xact_lock`으로 프로세스 간 직렬화된다.
- DB 미연결 환경(pool=None, 테스트)에서는 현행 메모리 전용 동작이 그대로 유지된다.
- 추후 사용자 토큰을 `scope` 컬럼 확장(`user:{id}`)으로 수용 가능한 스키마다.

## 설계

### 접근 방식

`get_access_token` 흐름 (state.lock 은 현행 유지):

```
 ├─ 1. 메모리 토큰 유효(만료 10분 전 마진) → 반환
 ├─ 2. pool 있으면 DB 조회 → 유효 → 메모리 캐시 + 반환
 ├─ 3. pool 있으면: pool.acquire → transaction → pg_advisory_xact_lock
 │     → DB 재조회(double-check) → 유효 → 캐시
 │     → 아니면 _issue_token(HTTP) → 같은 tx에서 upsert → 캐시
 └─ 4. pool 없으면: 현행 _issue_token 만 (동작 불변)
```

설계 근거 (검증 완료):
- `db_ops/trades_repo.py:32`의 `pg_advisory_xact_lock(hashtextextended($1, 0))` 패턴 재사용.
  session-level advisory lock 은 pooler(Supavisor transaction mode)에서 leak → xact lock 필수.
- DATABASE_URL은 `postgres`(테이블 owner) role 접속 → RLS enable + 정책 없음이면 BE(owner)는 통과,
  anon/authenticated(PostgREST)는 차단. 토큰 store는 `acquire_for_user`가 아닌 plain `pool.acquire()` 사용.
- `configure_kis` 호출처는 `main.py` lifespan + 테스트뿐 (scripts/는 KIS 미사용) → pool 배선은 lifespan 한 곳.
- 락 보유 중 HTTP 호출(커넥션 점유)은 하루 1~4회라 허용. 발급 실패는 현행대로 None 수렴(공급자 체인 fallback).

### 주요 변경 파일

- `supabase/migrations/028_kis_tokens.sql` — `kis_tokens(scope pk, access_token, expires_at, issued_at)` + RLS enable·정책 없음 (비밀 데이터 — stocks 류의 "RLS 미적용" 패턴과 다름, comment 로 사유 명시)
- `be/src/invest_note_api/external/kis_token_store.py` — load / issue_lock / load_in / save_in (kis.py import 금지 — 순환 방지)
- `be/src/invest_note_api/external/kis.py` — `KisState.pool` 추가, `configure_kis(settings, pool=None)`, `get_access_token` 3단 흐름, docstring 갱신
- `be/src/invest_note_api/main.py` — lifespan에서 pool 생성을 앞으로 이동 후 `configure_kis(settings, pool=app.state.pool)`
- `be/tests/test_kis.py` — `FakePool`/`FakeConnection`(advisory lock no-op 지원 확인됨) 재사용한 신규 테스트

## 구현 체크리스트

- [x] `supabase/migrations/028_kis_tokens.sql` 작성
- [x] `be/src/invest_note_api/external/kis_token_store.py` 작성
- [x] `be/src/invest_note_api/external/kis.py` 수정 (pool 통합)
- [x] `be/src/invest_note_api/main.py` lifespan 배선
- [x] `be/tests/test_kis.py` 테스트 추가 (DB-hit 시 발급 0회 / 미스 시 발급 1회+upsert / 재시작 재사용 / pool=None 회귀)
- [x] 전체 테스트 통과 (`cd be && poetry run pytest -q`) — 481 passed, 실패 4건은 develop에서도 동일한 기존 env 의존 이슈(공급자 기본값)로 이번 변경과 무관
- [x] 로컬 supabase 마이그레이션 적용 (`supabase migration up`) — 테이블 생성·RLS enable 확인

## 우려사항 / 리스크

- "신규 발급 시 기존 토큰 즉시 무효화" 여부는 KIS 문서상 미확정. 6시간 내 재호출은 동일 토큰 반환이라
  race 는 대부분 무해하지만, advisory lock 은 방어적으로 유지한다 (비용 미미).
- 멀티워커 전환 시: KIS가 토큰 거부 응답을 주면 재발급 전 DB 재조회(타 워커의 신규 토큰 픽업) 로직이
  추가로 필요 — 이번 범위 밖 (future note).
- 운영 DB 마이그레이션 적용 명령은 안내만 하고 직접 실행하지 않는다.
- **운영 ownership 가정**: RLS enable + 정책 없음 설계는 BE 접속 role 이 테이블 owner 일 때만 통과한다.
  로컬은 마이그레이션·앱 모두 `postgres` 접속이라 성립(실 DB 라운드트립으로 검증 완료). 운영에서
  마이그레이션 실행 role 과 앱 접속 role 이 달라지면 `load()`가 조용히 None → 매 요청 재발급 →
  EGW00133 으로 이어진다. 운영 배포 후 토큰 영속 동작 1회 확인 필요.
- **DB 장애 시 fail-closed (의도된 변경)**: pool 설정 상태에서 DB 접근 실패 시 종전처럼 직접 발급하지
  않고 None 수렴 → KIS 공급자 비활성. KIS 는 공급자 체인의 fallback 이고 메모리 캐시가 warm path 를
  커버하므로 허용. DB 다운이면 앱 전체가 불능이라 별도 우회는 과설계로 판단.

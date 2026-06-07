# Spec: BE 양쪽 prefix 동시 지원 (`/api/*` + `/*`)

> 완료: 2026-05-21

## 배경 / 문제

현재 BE FastAPI 라우터는 모두 `/api/*` prefix 를 갖는다. 운영 도메인은 이미
`api.invest-note.pixelwave.app` 서브도메인으로 분리되어 있어 `/api` prefix 는 의미상 중복이다.
다만 다음 두 제약으로 한 번에 prefix 를 제거할 수 없다:

1. 모바일 앱(Capacitor Android) — JS 번들이 빌드 시 박혀 설치되므로, 기존 설치 사용자는
   강제 업데이트 전까지 옛 `/api/*` 경로로 호출한다. BE 가 한쪽만 지원하면 전체 기능 마비.
2. BE/FE 별도 배포 — 동시 배포 보장 어려움.

본 spec 은 1단계로 **BE 가 신/구 prefix 를 동시에 지원**하도록 만들어, FE/앱 마이그레이션을
이후 독립적으로 진행할 수 있는 안전 마진을 확보한다.

## 목표

- 동일 엔드포인트가 `/api/<resource>` 와 `/<resource>` 두 경로 모두에서 동일 응답.
- 새 경로(`/<resource>`)는 OpenAPI 스키마에 노출. legacy(`/api/<resource>`)는 스키마에서 숨김.
- 기존 BE 테스트 슈트가 새 SOT 경로로 통과 + legacy 동등성 smoke 통과.
- FE/모바일 앱은 본 spec 범위 밖.

## 설계

### 접근 방식

각 라우터의 `prefix` 를 짧은 형태로 단축하고, `main.py` 에서 라우터를 두 번 등록한다:

```python
application.include_router(me.router)                                        # 새 SOT, OpenAPI 노출
application.include_router(me.router, prefix="/api", include_in_schema=False)  # legacy alias
```

`include_in_schema=False` 로 OpenAPI/Swagger UI 중복 노출을 방지한다.
`health.router` 는 `/healthz` 단독이고 `/api/healthz` 가 원래 없었으므로 dual 등록 불필요.

테스트는 **신 경로로 일괄 치환**하고, legacy alias 동등성은 신규 `test_legacy_api_prefix.py`
한 곳에서 대표 엔드포인트(`/me`, `/accounts`, `/portfolio/summary`, `/analysis/dashboard`)에
대해 status + body 비교로 검증한다.

### 주요 변경 파일

- `be/src/invest_note_api/routers/accounts.py` — prefix `/api/accounts` → `/accounts`
- `be/src/invest_note_api/routers/trades.py` — prefix `/api/trades` → `/trades`
- `be/src/invest_note_api/routers/portfolio.py` — prefix `/api/portfolio` → `/portfolio`
- `be/src/invest_note_api/routers/stocks.py` — prefix `/api/stocks` → `/stocks`
- `be/src/invest_note_api/routers/analysis.py` — prefix `/api/analysis` → `/analysis`
- `be/src/invest_note_api/routers/me.py` — prefix `/api/me` → `/me`
- `be/src/invest_note_api/main.py` — 6개 라우터 legacy alias 등록 추가
- `be/tests/test_{accounts,trades,portfolio,stocks,analysis,me}.py` — `/api/` → `/` 일괄 치환
- `be/tests/test_legacy_api_prefix.py` (신규) — legacy alias 동등성 smoke
- `fe/src/lib/api-client.ts` — ROUTES 객체 14곳 `/api/` 제거 (호출 SOT 를 새 경로로 전환)
- `fe/src/lib/analysis/{aggregate,rules}.ts` — 주석 내 `/api/analysis/dashboard` 표기 정리
- `docs/decisions.md` — 결정 기록 추가

### 범위 밖 (follow-up spec)

- 모바일 앱 강제 업데이트 게이트 + 새 번들 배포 (옛 설치 사용자는 현재 BE legacy alias 가 흡수)
- BE legacy alias 제거(sunset) — 옛 모바일 앱 점유율이 충분히 줄어든 시점
- `be/README.md` curl 예시 / `docs/backlog.md` 표기 정리

## 구현 체크리스트

- [x] 6개 라우터 파일 prefix 단축 (`/api/xxx` → `/xxx`)
- [x] `main.py` 에 legacy alias 등록 6건 추가
- [x] 기존 BE 테스트 6개 파일 `/api/` → `/` 일괄 치환
- [x] `be/tests/test_legacy_api_prefix.py` 신규 작성 (대표 4개 엔드포인트 동등성 smoke)
- [x] `docs/decisions.md` 결정 기록 추가
- [x] `cd be && poetry run pytest -q` 전체 통과 (287 passed)
- [x] 로컬 기동 후 신/구 경로 동등 응답 확인 + OpenAPI 에 `/api/*` 미노출 확인
- [x] FE `api-client.ts` ROUTES 의 `/api/` 제거 + 주석 정리
- [x] `pnpm -C fe exec tsc --noEmit` 통과
- [x] `pnpm -C fe test` 통과 (125 passed)

## 우려사항 / 리스크

- **OpenAPI operation_id 중복 경고**: 동일 라우터를 두 번 include 하면 FastAPI 가 경고를
  낼 수 있다. legacy 쪽 `include_in_schema=False` 로 스키마 영향은 없으나 기동 로그 확인 필요.
- **인증/RLS 의존성**: prefix 변경은 path 만 바꾸므로 dependency injection / RLS 컨텍스트에
  영향 없음. 안전.
- **롤백**: 본 spec 은 BE 내부 변경만 — FE/앱 변경이 없어 단일 PR revert 로 원복 가능.

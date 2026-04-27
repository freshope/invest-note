# Spec: MVP 해외 주식 제외

> Completed: 2026-04-27

## Background / Problem

MVP 범위에서 해외 주식을 제외하고 v2로 이동한다. 현재 문서와 일부 신규 입력/시세 경로에는 US/Yahoo 전제가 남아 있어 MVP 사용자가 해외 종목에 새로 진입하거나 시세를 조회할 수 있다.

## Goals

- 신규 해외 주식 검색·시세·매수 등록 경로를 MVP에서 차단한다.
- 기존 US/OTHER 데이터 조회와 화면 렌더링은 깨지지 않게 유지한다.
- 로드맵, 백로그, 결정 로그를 MVP=국내 주식 / v2=해외 주식 지원 방향에 맞게 갱신한다.

## Design

### Approach

백엔드 API 경계에서 KR 외 신규 매수와 US 시세/검색을 막고, 프론트엔드 입력 UI는 한국 종목 중심으로 정리한다. DB 타입과 기존 데이터 표시 로직, 기존 해외 보유분 매도는 호환성 때문에 유지한다.

### Primary Files

- `api/src/invest_note_api/routers/stocks.py` - 검색/시세 MVP 범위를 KR로 제한
- `api/src/invest_note_api/schemas/trade.py` - 신규 매수 생성 시 KR 외 country 거절
- `app/src/components/records/StockSearchInput.tsx` - 한국 종목 입력 UX로 정리
- `docs/roadmap.md`, `docs/backlog.md`, `docs/decisions.md` - 해외 주식 v2 이동 문서화

## Implementation Checklist

- [x] API 검색/시세에서 해외 주식 신규 사용 경로 차단
- [x] 거래 생성 검증에서 KR 외 신규 매수 차단
- [x] 프론트엔드 신규 매수 종목 입력을 KR 중심으로 정리
- [x] 테스트 갱신 및 문서 업데이트
- [x] Type check passes (`pnpm -C app exec tsc --noEmit`)
- [x] API tests pass (`cd api && poetry run pytest -q`)

## Risks / Open Questions

- 기존 US/OTHER 데이터는 유지하므로 v2 재도입 전까지 기존 해외 보유분의 신규 시세는 표시되지 않을 수 있다.

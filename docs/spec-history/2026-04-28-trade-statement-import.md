> 완료: 2026-04-28

# Spec: 증권사 거래내역서 파일 업로드 import

## 배경 / 문제

MVP 잔여 항목인 "CSV 임포트"가 미구현 상태. `CsvUploadButton.tsx`는 toast만 표시하는 placeholder이며 백엔드에 파서·업로드 라우터·엑셀/PDF 의존성이 전혀 없다. `sample/`에 삼성증권 xlsx와 토스증권 PDF 거래내역서가 있어 실 데이터 기반 파서로 MVP를 구현한다.

## 목표

- 파일 업로드 버튼 클릭 → 파일 선택 → preview(신규/중복/오류 카운트 확인) → commit → 결과 보고 흐름이 동작한다.
- 삼성증권 xlsx, 토스증권 PDF를 파일명 패턴으로 자동 감지하고 거래를 등록한다.
- 기 등록된 거래는 시그니처(날짜·종목·BUY/SELL·수량·가격) 비교로 중복 판단해 skip, 사용자 메타(strategy_type/reasoning_tags/emotion 등)가 보존된다.
- KRX 종목 master 테이블로 종목명 → ticker 변환이 동작한다.
- 새 파서 1개 추가 = 구현 1파일로 가능한 확장 구조를 갖는다.

## 설계

### 핵심 결정사항

| 항목 | 결정 |
|---|---|
| 중복 처리 | B안: `(account_id, date(traded_at), ticker_or_asset_name, trade_type, quantity, price)` dedup. traded_at은 날짜 단위만 비교 |
| ticker 해결 | KRX 종목 master (`kr_stocks` 테이블) lookup |
| 외화 처리 | MVP skip — 결과 보고서에 "USD N건 제외" 표시 |
| 트랜잭션 | preview/commit 분리. commit은 그룹별 lock + bulk insert + recalc 1회 |
| Preview staging | 메모리 TTL 캐시 (`cachetools.TTLCache`, ttl=10분) |
| 자동 증권사 감지 | 파일명 정규식 → 확장자 → 헤더 시그니처 순. 실패 시 수동 선택 |

### 파서 정규형 (ParsedTrade 필드)

`source_row_no`, `traded_at_kst`(KST naive), `trade_type`(BUY/SELL), `asset_name`, `ticker_hint`, `quantity`, `price`, `commission`, `tax`, `currency`(KRW/USD), `account_hint`, `raw`

### 주요 변경 파일

**신규 (백엔드)**
- `api/src/invest_note_api/broker_import/base.py` — ABC + ParsedTrade/ParseResult dataclass
- `api/src/invest_note_api/broker_import/__init__.py` — PARSERS dict + detect_broker()
- `api/src/invest_note_api/broker_import/samsung_xlsx.py` — 삼성증권 xlsx 파서
- `api/src/invest_note_api/broker_import/toss_pdf.py` — 토스증권 pdf 파서
- `api/src/invest_note_api/broker_import/ticker_resolver.py` — kr_stocks lookup
- `api/src/invest_note_api/domain/trade_import.py` — 시그니처/버킷팅/ImportSummary
- `api/src/invest_note_api/db_ops/kr_stocks_repo.py` — kr_stocks name→ticker lookup
- `api/src/invest_note_api/schemas/trade_import.py` — Pydantic 스키마
- `api/scripts/seed_kr_stocks.py` — KRX listing seed
- `supabase/migrations/014_create_kr_stocks.sql` — kr_stocks 테이블

**수정 (백엔드)**
- `api/pyproject.toml` — openpyxl/pdfplumber/python-multipart 추가
- `api/src/invest_note_api/db_ops/trades_repo.py` — insert_trades_bulk, list_trades_in_range 추가
- `api/src/invest_note_api/routers/trades.py` — /import/preview, /import/commit 추가

**신규 (프론트엔드)**
- `app/src/components/records/ImportTradesPanel/index.tsx` — FullScreenPanel + 4단계 상태기
- `app/src/components/records/ImportTradesPanel/BrokerStep.tsx`
- `app/src/components/records/ImportTradesPanel/FileStep.tsx`
- `app/src/components/records/ImportTradesPanel/PreviewStep.tsx`
- `app/src/components/records/ImportTradesPanel/ResultStep.tsx`

**수정 (프론트엔드)**
- `app/src/components/records/CsvUploadButton.tsx` — Panel trigger로 교체

## 구현 체크리스트

### Phase 1 — 종목 master & 의존성
- [x] `api/pyproject.toml` 의존성 3개 추가 + `poetry lock`
- [x] `supabase/migrations/014_create_kr_stocks.sql` 작성
- [x] `api/scripts/seed_kr_stocks.py` 작성
- [x] `api/src/invest_note_api/db_ops/kr_stocks_repo.py` + 단위 테스트

### Phase 2 — 파서 모듈
- [x] `domain/trade_import.py` — 시그니처/버킷팅 순수 함수 + 테스트
- [x] `broker_import/base.py` — ABC + dataclass
- [x] `broker_import/samsung_xlsx.py` + 익명화 fixture 기반 단위 테스트
- [x] `broker_import/toss_pdf.py` + 익명화 fixture 기반 단위 테스트
- [x] `broker_import/ticker_resolver.py` + 테스트
- [x] `broker_import/__init__.py` — PARSERS + detect_broker() + 테스트

### Phase 3 — 라우터·일괄 INSERT
- [x] `db_ops/trades_repo.py` — insert_trades_bulk, list_trades_in_range
- [x] `schemas/trade_import.py`
- [x] `routers/trades.py` — /import/preview, /import/commit + staging cache
- [x] 통합 테스트 (happy path, 재import, SELL 순서, USD skip)
- [x] `cd api && poetry run pytest -q` 통과

### Phase 4 — 프론트엔드
- [x] `app/src/lib/api/` — importPreview/importCommit 클라이언트
- [x] `ImportTradesPanel/index.tsx` 단계 상태기
- [x] `BrokerStep.tsx` / `FileStep.tsx` / `PreviewStep.tsx` / `ResultStep.tsx`
- [x] `CsvUploadButton.tsx` — Panel trigger로 변경
- [x] `pnpm -C app exec tsc --noEmit` 통과
- [x] `pnpm -C app test` 통과

### Phase 5 — 통합 검증
- [x] sample/ 실제 파일 두 개 dogfood import → 거래 목록·분석 탭 확인
- [x] 같은 파일 재import 시 신규 0건 (dedup 동작 확인)
- [x] 미감지 파일 업로드 시 수동 증권사 선택 흐름 확인

## 우려사항 / 리스크

- **종목 master 부담**: seed 출처(pyKRX vs 정적 CSV) 및 갱신 주기는 구현 중 결정
- **ticker 미해결 정책**: kr_stocks lookup 실패 시 (a) error 강등 + preview 카운트 노출 (기본 가정) vs (b) asset_name 폴백 — 구현 중 재확인
- **분할체결 dedup 한계**: 수동 등록 거래가 가격 반올림 차이로 dup 인식 실패 가능 → preview에서 확인 후 commit으로 수용
- **PDF 파싱 정확도**: 매도 행 셀 정렬 어긋남 위험 → pdfplumber 좌표 기반 + fixture 회귀 테스트
- **Preview staging**: 멀티 워커 환경에서 TTL 캐시 워커 미스 → MVP 단일 워커 가정, 향후 DB 임시 테이블로 교체
- **샘플 파일 익명화**: 테스트 fixture는 `api/tests/fixtures/broker_import/`에 익명화 사본 보관

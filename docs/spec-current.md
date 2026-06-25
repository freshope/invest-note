# 현재 작업 사양 — 거래내역서 일괄등록 파서 2종 추가 (Phase 1: 국내 KRW)

승인된 플랜: `/Users/jwlee/.claude/plans/sample-kb-valiant-tulip.md` (Phase 1 범위만).

> **범위 변경(사용자 요청):** KB증권은 이번 범위에서 제외 — 매도 거래 포함 샘플이 확보되면 추후 진행.
> 이번 작업은 **신한투자증권(shinhan_pdf) + 미래에셋증권(mirae_pdf) 2종만**. BE-1(KB)·FE의 KB 항목은 보류.

## 목표

`sample/` 에 추가된 3개 증권사 거래내역서를 일괄등록(import)으로 처리하도록 파서를 추가한다.
기존 파서 패턴(`api/src/invest_note_api/broker_import/samsung_xlsx.py`, `toss_pdf.py`)을 그대로 따른다.
**Phase 1 은 국내(KRW)만.** 해외(USD) 행은 기존 삼성/토스처럼 skip + `usd_skip_count` 증가. Phase 2(해외)는 범위 외.

import 파이프라인(`routers/trades.py` `/import/preview`·`commit`), dedup/머지(`domain/trade_import.py`),
ticker resolver(`broker_import/ticker_resolver.py`), `base.py` 는 **변경 없음** — 새 파서만 PARSERS 에 꽂는다.

## 작업 단위

### BE-1. KB증권 xlsx 파서 — **이번 범위 제외(보류)**
- 사용자 요청으로 KB증권은 제외한다. 매도 거래가 포함된 KB증권 거래내역서가 확보되면 추후 별도 작업으로 매수+매도 함께 구현.

### BE-2. 신한투자증권 PDF — `broker_import/shinhan_pdf.py` (key `shinhan_pdf`, "신한투자증권")
- pdfplumber 줄 단위. **거래 1건 = 3줄**:
  - line1: `<YYYY-MM-DD> <종목명> <단가> <수수료> <소득세> <신용금액> <미수처리금> <총변제금>`
  - line2: `<거래순번> <거래구분> <수량> <거래세> <지방소득세> ... <처리구분(공백포함)>`
  - line3: `<상품구분> <과표금액=수량×단가> <농특세> <정산금액> <예수금잔고>`
- **앵커**: line2 가 `^\d+\s+(장내_매수|장내_매도)\s` + line3 가 `위탁(주식)` 일 때만 거래. RP_*(위탁(RP) CMA)·기타 skip.
- 실측 29건 정합: `수량×단가 == line3 과표금액`. BUY/SELL=거래구분. commission=line1 수수료, tax=line2 거래세. account_hint=`계좌번호 : 270-26-192214`.

### BE-3. 미래에셋증권 PDF — `broker_import/mirae_pdf.py` (key `mirae_pdf`, "미래에셋증권")
- ⚠️ 암호화: `거래내역증명서_미래에셋증권_1.pdf` 는 AES 암호(`/V 4 /R 4`) → pdfplumber 예외. **fixture·구현 기준은 `_2.pdf`(비암호)**. 런타임 암호 PDF 업로드 시 예외를 잡아 `APIError`/`add_error("암호 없는 버전으로 재출력")` 친절 안내(빈 결과 금지).
- **거래 1건 = 2줄(긴 ETF명은 줄바꿈 3줄)**:
  - line1: `<YYYY/MM/DD> (주식매수입고|주식매도출고) A<6자리> <거래금액>`
  - line2: `<거래번호> <원번호> <수량> <단가> <종목명...> [<제세금합>] <유가잔고>`
- **앵커**: line1 `주식매수입고`(BUY)/`주식매도출고`(SELL) + `A\d{6}`. 이체입고/출고·주식매수출금/매도입금(현금leg)·공모주*·배당*·은행이체* skip.
- **종목명 공백 처리**: 숫자 앵커 — 앞 4토큰(거래번호/원번호/수량/단가), 뒤 1~2 숫자토큰(제세금합?/유가잔고), 가운데를 종목명 join. 줄바꿈 잔여 줄 이어붙임.
- 실측 25건: `수량×단가 == 거래금액`. ticker_hint=`A047810`→`047810`(토스 `_parse_ticker_hint` 규칙). account_hint=`계좌번호 584-566838640`. tax=제세금합(매도).

### BE-4. 레지스트리 — `broker_import/__init__.py`
- `PARSERS` dict 에 3개 인스턴스 추가 (key: kb_xlsx, shinhan_pdf, mirae_pdf).

### BE-5. 실파일 fixture 회귀 테스트 — `tests/test_broker_parsers.py`
- `TestTossPdfParserFixture` 패턴(저장소 루트 `sample/` 실파일, 없으면 `pytest.skip`).
- 신한: 위탁(주식) 29건만(RP 제외), account_hint `270-26-192214`, 첫 건 한화엔진 SELL 2@49700, 수량×단가 정합.
- 미래에셋: 25건, account_hint `584-566838640`, ticker_hint(A코드), 첫 건 두산에너빌리티 BUY 10@105700, 긴 ETF명 레코드 정상 파싱.

### FE-1. 브로커 옵션 — `app/src/components/records/ImportTradesPanel/brokers.ts`
- `BrokerOption.key` 유니온에 `"mirae_pdf" | "shinhan_pdf"` 추가.
- `BROKER_OPTIONS` 2종 추가. **label 은 계좌 증권사명과 정확히 일치**(`findBrokerKeyByAccountBroker` 가 `label === account.broker`): `"미래에셋증권"`, `"신한투자증권"`.
- accept: 미래에셋/신한 `.pdf`. downloadGuide 각 작성 — 미래에셋 가이드에 "암호 없는 버전 출력" 안내.

### QA. 경계 정합 — integration-qa
- BE PARSERS 키 집합 == FE BROKER_OPTIONS 키 집합 (2종 동기화: shinhan_pdf, mirae_pdf).
- FE label == BROKERS(`app/src/lib/brokers.ts`) 증권사명 정확 일치.
- BE pytest + FE tsc/test 무회귀. fixture 단언 통과.

## 검증
- BE: `cd api && poetry run pytest tests/test_broker_parsers.py -q` (전체 `poetry run pytest -q`)
- FE: `pnpm -C app exec tsc --noEmit` + `pnpm -C app test`

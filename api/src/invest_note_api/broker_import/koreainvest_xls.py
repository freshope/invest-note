"""한국투자증권 거래내역서 파서.

한국투자증권 HTS/MTS 에서 내려받는 '거래내역서' 는 확장자가 .xls 이지만 실제로는
HTML 테이블(엑셀 위장)이다. openpyxl/xls 바이너리로는 열리지 않으므로 stdlib
html.parser 로 <tr>/<td> 를 추출한다.

거래 1건 = 데이터 2행:
  line1: 거래일 종목명 거래수량 환율 거래금액 수수료 유가잔고 잔액 상대계좌
  line2: 거래종류 잔고번호 거래단가 외환잔액 정산금액 거래세 세금 부가세 접속매체
"""

from __future__ import annotations

import re
from html.parser import HTMLParser as _HTMLParser

from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, TRADE_TYPE_SELL

from .base import BrokerStatementParser, ParsedTrade, ParseResult, parse_number

# line1: 계좌정보 셀에서 계좌번호 추출 ("69604881-01 (정영경)")
_ACCOUNT_RE = re.compile(r"(\d{6,}-\d{2,})")
_DATE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")

# 원장 raw 라벨 (열 순서 고정) — 컬럼 시프트 감지·무손실 덤프용.
_L1_HEADERS = ["거래일", "종목명", "거래수량", "환율", "거래금액", "수수료", "유가잔고", "잔액", "상대계좌"]
_L2_HEADERS = ["거래종류", "잔고번호", "거래단가", "외환잔액", "정산금액", "거래세", "세금", "부가세", "접속매체"]


class _TableExtractor(_HTMLParser):
    """HTML 표를 셀 문자열의 행 리스트로 추출한다. 셀 내부 태그·엔티티는 정규화한다."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).replace("\xa0", " ").strip())
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


class KoreaInvestXlsParser(BrokerStatementParser):
    key = "koreainvest_xls"
    display_name = "한국투자증권"

    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        result = ParseResult()
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("cp949", errors="replace")

        extractor = _TableExtractor()
        extractor.feed(text)
        rows = extractor.rows

        for r in rows:
            if r and r[0].startswith("계좌정보"):
                m = _ACCOUNT_RE.search(" ".join(r[1:]))
                if m:
                    result.account_hint = m.group(1)
                break

        row_no = 0
        i = 0
        n = len(rows)
        while i < n:
            r1 = rows[i]
            if not (r1 and _DATE_RE.match(r1[0]) and len(r1) >= 9):
                i += 1
                continue
            # 날짜로 시작하는 데이터 행 = line1. 다음 행이 line2(거래종류)여야 한다.
            r2 = rows[i + 1] if i + 1 < n else []
            row_no += 1
            if len(r2) < 8:
                raw = dict(zip(_L1_HEADERS, r1))
                result.add_error(row_no, f"line2 형식 불일치: {r2!r}", raw)
                result.add_non_trade(row_no, raw, kind="error")
                i += 1
                continue
            self._parse_pair(r1, r2, row_no, result)
            i += 2

        return result

    def _parse_pair(
        self, r1: list[str], r2: list[str], row_no: int, result: ParseResult
    ) -> None:
        # 행 원문 전체 덤프 (원장 무손실 책임).
        raw = dict(zip(_L1_HEADERS, r1))
        raw.update(dict(zip(_L2_HEADERS, r2)))

        kind = r2[0]
        if "매수" in kind:
            trade_type = TRADE_TYPE_BUY
        elif "매도" in kind:
            trade_type = TRADE_TYPE_SELL
        else:  # 배당·입출금 등 비거래 행
            result.add_error(row_no, f"미지원 거래종류: {kind}", raw)
            result.add_non_trade(row_no, raw)
            return

        # 환율 > 0 = 외화(해외) 거래 — MVP 미지원(토스만 해외 지원). 보수적으로 스킵.
        if parse_number(r1[3]) > 0:
            result.usd_skip_count += 1
            result.add_error(row_no, "해외(외화) 거래 — MVP 미지원", raw)
            result.add_non_trade(row_no, raw)
            return

        asset_name = r1[1].strip()
        if not asset_name:
            result.add_error(row_no, "종목명 없음", raw)
            result.add_non_trade(row_no, raw, kind="error")
            return

        traded_at_kst = r1[0].replace(".", "-")  # "2026.04.28" -> "2026-04-28"
        quantity = parse_number(r1[2])
        price = parse_number(r2[2])
        commission = parse_number(r1[5])
        # 거래세 + 세금 + 부가세 합 (국내주식은 거래세만 있고 나머지는 0).
        tax = parse_number(r2[5]) + parse_number(r2[6]) + parse_number(r2[7])

        if quantity <= 0 or price <= 0:
            result.add_error(row_no, f"수량({quantity}) 또는 단가({price})가 0 이하", raw)
            result.add_non_trade(row_no, raw, kind="error")
            return

        # 거래금액 == 수량 × 단가 (컬럼 시프트 감지 가드).
        gross = parse_number(r1[4])
        if gross and abs(quantity * price - gross) > 1.0:
            result.add_error(
                row_no, f"거래금액 불일치 (수량×단가={quantity * price}, 거래금액={gross})", raw
            )
            result.add_non_trade(row_no, raw, kind="error")
            return

        result.add_trade(
            ParsedTrade(
                source_row_no=row_no,
                traded_at_kst=traded_at_kst,
                trade_type=trade_type,
                asset_name=asset_name,
                quantity=quantity,
                price=price,
                commission=commission,
                tax=tax,
                currency="KRW",
                account_hint=result.account_hint,
                raw=raw,
            ),
            raw=raw,
        )

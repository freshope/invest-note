"""신한투자증권 거래내역서 PDF 파서.

거래 1건 = 3줄. line2(거래순번 거래구분 ...) 를 앵커로 잡고, 직전 줄(line1)·다음 줄
(line3) 을 함께 묶는다. RP_* (위탁(RP)) 등 비주식 행은 앵커 조건에서 자연히 배제된다.

  line1: <YYYY-MM-DD> <종목명> <단가> <수수료> <소득세> <신용금액> <미수처리금> <총변제금>
  line2: <거래순번> <거래구분> <수량> <거래세> <지방소득세> ... <처리구분...>
  line3: <상품구분> <과표금액=수량×단가> <농특세> <정산금액> ... <예수금잔고>
"""

from __future__ import annotations

import re

from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, TRADE_TYPE_SELL

from .base import (
    BrokerStatementParser,
    ParsedTrade,
    ParseResult,
    extract_pdf_lines,
    parse_number,
)

_ACCOUNT_RE = re.compile(r"계좌번호\s*:\s*([\d\-]+)")
# line2 앵커: "1 장내_매도 2 49 ..." / "2 장내_매수 2 0 ..."
_LINE2_RE = re.compile(r"^(?P<seq>\d+)\s+장내_(?P<klass>매수|매도)\s+(?P<rest>.+)$")
_LINE3_PREFIX = "위탁(주식)"
# line1: "2026-01-13 한화엔진 49,700 0 0 0 99,400 0"
_LINE1_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<rest>.+)$")
_NUM_RE = re.compile(r"^[\d,]+(?:\.\d+)?$")


class ShinhanPdfParser(BrokerStatementParser):
    key = "shinhan_pdf"
    display_name = "신한투자증권"

    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        result = ParseResult()
        extracted = extract_pdf_lines(file_bytes, _ACCOUNT_RE)
        if extracted is None:
            result.add_error(
                0, "PDF 를 열 수 없습니다. 암호 없는 버전으로 재출력 후 업로드해 주세요."
            )
            return result
        result.account_hint, lines = extracted

        row_counter = 0
        for i in range(1, len(lines) - 1):
            m2 = _LINE2_RE.match(lines[i])
            if not m2:
                continue
            if not lines[i + 1].startswith(_LINE3_PREFIX):
                continue

            row_counter += 1
            parsed = self._parse_record(
                lines[i - 1], lines[i], lines[i + 1], m2, row_counter, result
            )
            if parsed:
                result.trades.append(parsed)

        return result

    def _parse_record(
        self,
        line1: str,
        line2: str,
        line3: str,
        m2: re.Match,
        row_no: int,
        result: ParseResult,
    ) -> ParsedTrade | None:
        m1 = _LINE1_RE.match(line1)
        if not m1:
            result.add_error(row_no, f"line1 형식 불일치: {line1!r}")
            return None

        klass = m2.group("klass")
        trade_type = TRADE_TYPE_BUY if klass == "매수" else TRADE_TYPE_SELL

        # line1: 종목명(공백·숫자 포함 가능) + 끝의 6개 값 컬럼
        #        (단가 수수료 소득세 신용금액 미수처리금 총변제금).
        # 종목명에 숫자 토큰이 있어도 밀리지 않도록 '첫 숫자' 가 아니라 '끝 6개' 를 앵커한다.
        line1_tokens = m1.group("rest").split()
        if len(line1_tokens) < 7 or not all(_NUM_RE.match(t) for t in line1_tokens[-6:]):
            result.add_error(row_no, f"단가/종목명 추출 불가: {line1!r}")
            return None
        asset_name = " ".join(line1_tokens[:-6]).strip()
        price = parse_number(line1_tokens[-6])
        commission = parse_number(line1_tokens[-5])

        # line2: 수량 거래세 (거래구분 뒤 첫 두 숫자 토큰).
        line2_tokens = m2.group("rest").split()
        quantity = parse_number(line2_tokens[0]) if line2_tokens else 0.0
        tax = parse_number(line2_tokens[1]) if len(line2_tokens) > 1 else 0.0

        if quantity <= 0 or price <= 0:
            result.add_error(row_no, f"수량({quantity}) 또는 단가({price})가 0 이하")
            return None

        # line3: 과표금액 = 수량 × 단가 (정합성 가드).
        line3_tokens = line3.split()
        base_amount = parse_number(line3_tokens[1]) if len(line3_tokens) > 1 else 0.0
        if base_amount and abs(quantity * price - base_amount) > 1.0:
            result.add_error(
                row_no,
                f"과표금액 불일치 (수량×단가={quantity * price}, 과표={base_amount})",
                {"line1": line1, "line2": line2, "line3": line3},
            )
            return None

        return ParsedTrade(
            source_row_no=row_no,
            traded_at_kst=m1.group("date"),
            trade_type=trade_type,
            asset_name=asset_name,
            quantity=quantity,
            price=price,
            commission=commission,
            tax=tax,
            currency="KRW",
            account_hint=result.account_hint,
            raw={"line1": line1, "line2": line2, "line3": line3},
        )

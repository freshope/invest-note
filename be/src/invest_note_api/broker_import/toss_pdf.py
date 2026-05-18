"""토스증권 거래내역서 PDF 파서."""

from __future__ import annotations

import io
import re

import pdfplumber

from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, TRADE_TYPE_SELL

from .base import BrokerStatementParser, ParsedTrade, ParseResult, parse_number

_FILENAME_RE = re.compile(r"^토스증권_거래내역서_\d{8}_\d{8}_\d+\.pdf$")
_ACCOUNT_RE = re.compile(r"계좌\s*번호\s+([\d\-]+)")
# KRX 6자리 코드. 우선주는 'A' 접두사가 붙는 경우가 있어(예: A005935) A?로 허용.
_TICKER_RE = re.compile(r"^(.+?)\(A?(\d{6})\)$")

# 데이터 행 패턴: "<YYYY.MM.DD or YYYY-MM-DD> <구매|판매> <name(code)> <숫자들...>"
# 종목명은 공백을 포함할 수 있으므로 비탐욕 매칭 + 종목코드 패턴으로 경계를 잡는다.
_DATA_LINE_RE = re.compile(
    r"^(?P<date>\d{4}[.\-]\d{2}[.\-]\d{2})\s+"
    r"(?P<klass>구매|판매)\s+"
    r"(?P<name>.+?\(A?\d{6}\))\s+"
    r"(?P<rest>.+)$"
)

_KRW_SECTION = "원화 거래내역"
_USD_SECTION = "달러 거래내역"


def _parse_ticker_hint(raw_name: str) -> tuple[str, str | None]:
    """'삼성전자(A005930)' → ('삼성전자', '005930')"""
    m = _TICKER_RE.match(raw_name.strip())
    if m:
        return m.group(1).strip(), m.group(2)
    return raw_name.strip(), None


class TossPdfParser(BrokerStatementParser):
    key = "toss_pdf"
    display_name = "토스증권"

    @classmethod
    def match(cls, filename: str, head_bytes: bytes) -> bool:
        if _FILENAME_RE.match(filename):
            return True
        # PDF 매직 + 토스 시그니처
        if head_bytes[:4] == b"%PDF" and b"\xed\x86\xa0\xec\x8a\xa4\xec\xa6\x9d\xea\xb6\x8c" in head_bytes[:2048]:
            return True
        return False

    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        # pdfplumber.extract_tables() 는 토스 PDF 의 텍스트 레이아웃에서 테이블 경계를
        # 찾지 못해 빈 리스트만 반환한다. 따라서 페이지 텍스트를 줄 단위로 파싱한다.
        result = ParseResult()
        row_counter = 0

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            in_krw = False
            in_usd = False

            for page in pdf.pages:
                page_text = page.extract_text() or ""

                if result.account_hint is None:
                    m = _ACCOUNT_RE.search(page_text)
                    if m:
                        result.account_hint = m.group(1).strip()

                for line in page_text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue

                    if _KRW_SECTION in line:
                        in_krw, in_usd = True, False
                        continue
                    if _USD_SECTION in line:
                        in_krw, in_usd = False, True
                        continue

                    if not _DATA_LINE_RE.match(line):
                        continue

                    if in_usd:
                        result.usd_skip_count += 1
                        continue
                    if not in_krw:
                        continue

                    row_counter += 1
                    parsed = self._parse_line(line, row_counter, result)
                    if parsed:
                        result.trades.append(parsed)

        return result

    def _parse_line(self, line: str, row_no: int, result: ParseResult) -> ParsedTrade | None:
        """텍스트 한 줄을 파싱하여 ParsedTrade 를 반환한다.

        원화 거래내역 컬럼 (extract_text 토큰 순서):
            0: 거래일자
            1: 거래구분 ("구매" | "판매")
            2: 종목명(종목코드)
            3: 거래수량
            4: 거래대금
            5: 단가
            6: 수수료
            7: 거래세
            8: 제세금
            9: 변제/연체합
            10: 잔고
            11: 잔액

        환율 컬럼은 KRW 행에서 비어 있어 토큰으로 추출되지 않는다.
        """
        m = _DATA_LINE_RE.match(line)
        if not m:
            return None

        date_raw = m.group("date")
        klass = m.group("klass")
        name_raw = m.group("name")
        nums = m.group("rest").split()

        if klass == "구매":
            trade_type = TRADE_TYPE_BUY
        elif klass == "판매":
            trade_type = TRADE_TYPE_SELL
        else:
            result.add_error(row_no, f"알 수 없는 거래구분: {klass}")
            return None

        # 숫자 컬럼 9개(거래수량 ~ 잔액). 부족하면 행이 잘렸을 가능성.
        if len(nums) < 9:
            result.add_error(row_no, f"숫자 컬럼 부족 ({len(nums)}/9): {nums}")
            return None

        qty_raw, amount_raw, price_raw, fee_raw, tax_raw, sec_tax_raw = nums[:6]

        asset_name, ticker_hint = _parse_ticker_hint(name_raw)
        if not asset_name:
            result.add_error(row_no, "종목명 없음")
            return None

        quantity = parse_number(qty_raw)
        amount = parse_number(amount_raw)
        price = parse_number(price_raw)
        commission = parse_number(fee_raw)
        tax = parse_number(tax_raw) + parse_number(sec_tax_raw)

        if quantity <= 0:
            result.add_error(row_no, f"수량({quantity})이 0 이하")
            return None

        # 단가가 비어 있거나 0 이면 거래대금 / 수량 으로 보정.
        if price <= 0:
            price = round(amount / quantity, 4) if quantity > 0 else 0.0
        if price <= 0:
            result.add_error(row_no, f"단가 계산 불가 (거래대금={amount}, 수량={quantity})")
            return None

        traded_at_kst = date_raw.replace(".", "-")[:10]

        return ParsedTrade(
            source_row_no=row_no,
            traded_at_kst=traded_at_kst,
            trade_type=trade_type,
            asset_name=asset_name,
            quantity=quantity,
            price=price,
            commission=commission,
            tax=tax,
            currency="KRW",
            ticker_hint=ticker_hint,
            account_hint=result.account_hint,
            raw={"date": date_raw, "name": name_raw, "qty": qty_raw, "amount": amount_raw},
        )

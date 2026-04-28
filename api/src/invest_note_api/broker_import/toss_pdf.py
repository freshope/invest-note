"""토스증권 거래내역서 PDF 파서."""

from __future__ import annotations

import io
import re

import pdfplumber

from .base import BrokerStatementParser, ParsedTrade, ParseResult, parse_number

_FILENAME_RE = re.compile(r"^토스증권_거래내역서_\d{8}_\d{8}_\d+\.pdf$")
_ACCOUNT_RE = re.compile(r"계좌\s*번호\s+([\d\-]+)")
_TICKER_RE = re.compile(r"^(.+?)\(A?(\d{6})\)$")

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
        result = ParseResult()
        row_counter = 0

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            in_krw = False
            in_usd = False

            for page in pdf.pages:
                page_text = page.extract_text() or ""

                # 계좌번호 추출 (첫 페이지)
                if result.account_hint is None:
                    m = _ACCOUNT_RE.search(page_text)
                    if m:
                        result.account_hint = m.group(1).strip()

                # 섹션 감지
                if _KRW_SECTION in page_text:
                    in_krw = True
                    in_usd = False
                if _USD_SECTION in page_text:
                    in_usd = True
                    in_krw = False

                if in_usd:
                    # USD 섹션은 skip — 테이블만 카운트
                    tables = page.extract_tables()
                    for table in tables:
                        for row in (table or []):
                            if row and any(row):
                                result.usd_skip_count += 1
                    continue

                if not in_krw:
                    continue

                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if not row or not any(row):
                            continue
                        row_counter += 1

                        # 헤더 행 skip (거래일자가 리터럴 텍스트인 경우)
                        if str(row[0] or "").strip() in ("거래일자", ""):
                            continue

                        parsed = self._parse_row(row, row_counter, result)
                        if parsed:
                            result.trades.append(parsed)

        return result

    def _parse_row(self, row: list, row_no: int, result: ParseResult) -> ParsedTrade | None:
        """
        토스 PDF 원화 거래내역 컬럼 순서 (pdfplumber extract_table 기준):
        0: 거래일자
        1: 거래구분 ("구매" | "" | None)
        2: 종목명(종목코드)
        3: 환율
        4: 거래수량
        5: 거래대금 (또는 단가)
        6: 거래세
        7: 제세금
        8: 변제/연체합
        9: 잔고
        10: 잔액

        매도 행은 거래구분 셀이 비어 shift되는 경우가 있어 최소 컬럼 수로 보정한다.
        """
        cells = [str(c or "").strip() for c in row]
        while len(cells) < 11:
            cells.append("")

        date_raw = cells[0]
        if not re.match(r"\d{4}[.\-]\d{2}[.\-]\d{2}", date_raw):
            return None

        traded_at_kst = date_raw.replace(".", "-")[:10]

        # 거래구분 판단
        trade_class = cells[1]
        if trade_class == "구매":
            trade_type = "BUY"
            name_raw = cells[2]
            qty_raw = cells[4]
            amount_raw = cells[5]
            tax_raw = cells[6]
            sec_tax_raw = cells[7]
        elif trade_class == "":
            # 매도 행 — 셀이 하나 앞당겨짐
            trade_type = "SELL"
            name_raw = cells[1] if not re.match(r"\d{4}[.\-]\d{2}[.\-]\d{2}", cells[1]) else cells[2]
            qty_raw = cells[3]
            amount_raw = cells[4]
            tax_raw = cells[5]
            sec_tax_raw = cells[6]
        else:
            result.add_error(row_no, f"알 수 없는 거래구분: {trade_class}")
            return None

        asset_name, ticker_hint = _parse_ticker_hint(name_raw)
        if not asset_name:
            result.add_error(row_no, "종목명 없음")
            return None

        quantity = _parse_number(qty_raw)
        amount = _parse_number(amount_raw)
        tax = _parse_number(tax_raw) + _parse_number(sec_tax_raw)

        if quantity <= 0:
            result.add_error(row_no, f"수량({quantity})이 0 이하")
            return None

        # 단가 = 거래대금 / 수량 (토스 PDF에 단가 컬럼 없음)
        price = round(amount / quantity, 4) if quantity > 0 else 0.0
        if price <= 0:
            result.add_error(row_no, f"단가 계산 불가 (거래대금={amount}, 수량={quantity})")
            return None

        return ParsedTrade(
            source_row_no=row_no,
            traded_at_kst=traded_at_kst,
            trade_type=trade_type,
            asset_name=asset_name,
            quantity=quantity,
            price=price,
            commission=0.0,
            tax=tax,
            currency="KRW",
            ticker_hint=ticker_hint,
            account_hint=result.account_hint,
            raw={"date": date_raw, "name": name_raw, "qty": qty_raw, "amount": amount_raw},
        )

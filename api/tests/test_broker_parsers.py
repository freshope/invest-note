"""삼성증권 xlsx 파서 단위 테스트 (synthetic in-memory 파일 사용)."""

import io
from datetime import date

import openpyxl
import pytest

from invest_note_api.broker_import import PARSERS, detect_broker
from invest_note_api.broker_import.samsung_xlsx import SamsungXlsxParser


def _make_samsung_xlsx(rows: list[dict], account_meta: str = "7157197877-14 [ ISA ] 홍길동") -> bytes:
    """테스트용 삼성증권 xlsx 파일을 메모리에서 생성한다."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Col1"

    # A1: 계좌 메타
    ws["A1"] = account_meta
    ws["B1"] = "< 2026.01.01 ~ 2026.12.31 >"

    # 2행: 헤더
    headers = [
        "거래일자", "거래명", "거래수량", "거래금액", "제세금/대출이자",
        "현금잔액", "상대계좌명", "변제금액", "통화코드", "외화정산금액",
        "거래번호", "종목명", "거래단가", "정산금액", "수수료/Fee",
        "잔고수량/펀드평가금액", "상대계좌번호", "신용/대출금",
        "외화거래금액", "외화예수금액", "처리점",
    ]
    ws.append(headers)

    # 3행~: 데이터
    for row in rows:
        ws.append([row.get(h, "") for h in headers])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _buy_row(date_str="2026-03-30", name="매수", asset="삼성전자",
             qty=10, price=70000, fee=22, tax=0, currency="") -> dict:
    return {
        "거래일자": date_str,
        "거래명": name,
        "종목명": asset,
        "거래수량": qty,
        "거래단가": price,
        "거래금액": qty * price,
        "수수료/Fee": fee,
        "제세금/대출이자": tax,
        "통화코드": currency,
    }


class TestSamsungXlsxParser:
    parser = SamsungXlsxParser()

    def test_match_by_filename(self):
        assert SamsungXlsxParser.match("삼성증권 거래내역서.xlsx", b"PK")
        assert not SamsungXlsxParser.match("토스증권_거래내역.pdf", b"%PDF")

    def test_parses_buy_trade(self):
        xlsx = _make_samsung_xlsx([_buy_row()])
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.trade_type == "BUY"
        assert t.asset_name == "삼성전자"
        assert t.quantity == 10
        assert t.price == 70000
        assert t.commission == 22
        assert t.currency == "KRW"

    def test_parses_sell_trade(self):
        xlsx = _make_samsung_xlsx([_buy_row(name="매도", tax=350)])
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert len(result.trades) == 1
        assert result.trades[0].trade_type == "SELL"
        assert result.trades[0].tax == 350

    def test_nxt_trades_are_included(self):
        xlsx = _make_samsung_xlsx([
            _buy_row(name="매수_NXT"),
            _buy_row(name="매도_NXT"),
        ])
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert len(result.trades) == 2

    def test_non_trade_rows_are_errors(self):
        xlsx = _make_samsung_xlsx([
            _buy_row(name="배당금입금"),
            _buy_row(name="이체입금"),
            _buy_row(),
        ])
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert len(result.trades) == 1
        assert len(result.errors) == 2

    def test_usd_trade_skipped(self):
        row = _buy_row(currency="USD")
        xlsx = _make_samsung_xlsx([row])
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert len(result.trades) == 0
        assert result.usd_skip_count == 1

    def test_account_hint_extracted(self):
        xlsx = _make_samsung_xlsx([], account_meta="7157197877-14 [ ISA ] 홍길동")
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert result.account_hint == "7157197877-14"

    def test_zero_quantity_produces_error(self):
        row = _buy_row(qty=0)
        xlsx = _make_samsung_xlsx([row])
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert len(result.trades) == 0
        assert len(result.errors) == 1

    def test_multiple_trades(self):
        xlsx = _make_samsung_xlsx([
            _buy_row(date_str="2026-01-10", name="매수", asset="삼성전자", qty=5, price=70000),
            _buy_row(date_str="2026-02-01", name="매도", asset="삼성전자", qty=3, price=72000),
            _buy_row(date_str="2026-03-15", name="매수", asset="SK하이닉스", qty=10, price=150000),
        ])
        result = self.parser.parse(xlsx, "삼성증권 거래내역서.xlsx")
        assert len(result.trades) == 3
        assert result.trades[0].asset_name == "삼성전자"
        assert result.trades[1].trade_type == "SELL"
        assert result.trades[2].asset_name == "SK하이닉스"


class TestDetectBroker:
    def test_detects_samsung_by_filename(self):
        xlsx_bytes = _make_samsung_xlsx([])
        key = detect_broker("삼성증권 거래내역서.xlsx", xlsx_bytes)
        assert key == "samsung_xlsx"

    def test_detects_toss_by_filename(self):
        # 실제 PDF 바이트 없이 파일명으로만 감지
        fake_pdf = b"%PDF-1.4 " + b"\x00" * 100
        key = detect_broker("토스증권_거래내역서_20250417_20260416_1.pdf", fake_pdf)
        assert key == "toss_pdf"

    def test_returns_none_for_unknown(self):
        key = detect_broker("unknown_bank.xlsx", b"PK\x03\x04")
        assert key is None

    def test_parsers_registry_has_both_brokers(self):
        assert "samsung_xlsx" in PARSERS
        assert "toss_pdf" in PARSERS

"""증권사 파서 단위 테스트 (synthetic in-memory 파일 사용)."""

import io
from datetime import date

import openpyxl
import pytest

from invest_note_api.broker_import import PARSERS, detect_broker
from invest_note_api.broker_import.samsung_xlsx import SamsungXlsxParser
from invest_note_api.broker_import.toss_pdf import TossPdfParser, _parse_ticker_hint
from invest_note_api.broker_import.base import ParseResult


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


class TestParseTickerHint:
    def test_standard_ticker(self):
        name, code = _parse_ticker_hint("삼성전자(005930)")
        assert name == "삼성전자"
        assert code == "005930"

    def test_preferred_share_a_prefix(self):
        name, code = _parse_ticker_hint("삼성전자우(A005935)")
        assert name == "삼성전자우"
        assert code == "005935"

    def test_no_code_returns_none(self):
        name, code = _parse_ticker_hint("삼성전자")
        assert name == "삼성전자"
        assert code is None

    def test_strips_whitespace(self):
        name, code = _parse_ticker_hint("  SK하이닉스(000660)  ")
        assert name == "SK하이닉스"
        assert code == "000660"


def _make_toss_buy_row(
    date_str="2026-03-30",
    name="삼성전자(005930)",
    qty=10,
    amount=700000,
    tax=0,
    sec_tax=1260,
) -> list:
    """BUY 행 셀 목록 (pdfplumber extract_table 기준 포맷)."""
    return [date_str, "구매", name, "", str(qty), str(amount), str(tax), str(sec_tax), "", "", ""]


def _make_toss_sell_row(
    date_str="2026-04-15",
    name="삼성전자(005930)",
    qty=5,
    amount=365000,
    tax=730,
    sec_tax=365,
) -> list:
    """SELL 행 셀 목록 — 거래구분 셀이 빈 경우."""
    return [date_str, "", name, "", str(qty), str(amount), str(tax), str(sec_tax), "", "", ""]


class TestTossPdfParserRow:
    parser = TossPdfParser()

    def test_parses_buy_row(self):
        result = ParseResult()
        trade = self.parser._parse_row(_make_toss_buy_row(), 1, result)
        assert trade is not None
        assert trade.trade_type == "BUY"
        assert trade.asset_name == "삼성전자"
        assert trade.ticker_hint == "005930"
        assert trade.quantity == 10
        assert trade.price == pytest.approx(70000.0)
        assert trade.tax == pytest.approx(1260.0)

    def test_parses_sell_row(self):
        result = ParseResult()
        trade = self.parser._parse_row(_make_toss_sell_row(), 2, result)
        assert trade is not None
        assert trade.trade_type == "SELL"
        assert trade.asset_name == "삼성전자"
        assert trade.quantity == 5
        assert trade.price == pytest.approx(73000.0)
        assert trade.tax == pytest.approx(1095.0)

    def test_invalid_date_returns_none(self):
        result = ParseResult()
        row = ["거래일자", "구매", "삼성전자(005930)", "", "10", "700000", "0", "0", "", "", ""]
        trade = self.parser._parse_row(row, 3, result)
        assert trade is None
        assert len(result.errors) == 0

    def test_zero_quantity_produces_error(self):
        result = ParseResult()
        row = _make_toss_buy_row(qty=0)
        trade = self.parser._parse_row(row, 4, result)
        assert trade is None
        assert any("수량" in e["reason"] for e in result.errors)

    def test_dot_date_separator(self):
        result = ParseResult()
        row = _make_toss_buy_row(date_str="2026.03.30")
        trade = self.parser._parse_row(row, 5, result)
        assert trade is not None
        assert trade.traded_at_kst == "2026-03-30"

    def test_unknown_trade_class_produces_error(self):
        result = ParseResult()
        row = ["2026-03-30", "배당", "삼성전자(005930)", "", "10", "700000", "0", "0", "", "", ""]
        trade = self.parser._parse_row(row, 6, result)
        assert trade is None
        assert len(result.errors) == 1
        assert "알 수 없는 거래구분" in result.errors[0]["reason"]

    def test_match_by_filename(self):
        assert TossPdfParser.match("토스증권_거래내역서_20250417_20260416_1.pdf", b"%PDF")
        assert not TossPdfParser.match("삼성증권 거래내역서.xlsx", b"PK")


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

"""토스증권 거래내역서 PDF 파서."""

from __future__ import annotations

import io
import re

import pdfplumber

from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, TRADE_TYPE_SELL

from .base import BrokerStatementParser, ParsedTrade, ParseResult, parse_number

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

# 달러(USD) 섹션 데이터 행 패턴. 종목코드가 ISIN(영숫자 12자, 예 US69608A1088)이라
# KRW 용 `_DATA_LINE_RE`(6자리 코드)에 안 걸린다. KRW 무회귀를 위해 별도 정규식으로 분리.
# 구매/판매만 매칭 → 환전/배당/이자 등 비거래 행은 자연히 제외된다.
_USD_DATA_LINE_RE = re.compile(
    r"^(?P<date>\d{4}[.\-]\d{2}[.\-]\d{2})\s+"
    r"(?P<klass>구매|판매)\s+"
    r"(?P<name>.+?\([A-Z0-9]{12}\))\s+"
    r"(?P<rest>.+)$"
)
# ISIN 은 KRX 표준 숫자코드가 아니라 ticker_hint 로 쓰지 않는다(mirae A0080G0 선례).
# 대신 OpenFIGI 해소용으로 별도 isin 필드에 담는다(ParsedTrade.isin). group(2)=ISIN.
_USD_TICKER_RE = re.compile(r"^(.+?)\(([A-Z0-9]{12})\)$")
# 환율 앵커: '1,xxx.xx'(소수 2자리). glued 토큰 '1,370.300.004568' 디-글루용.
_USD_RATE_ANCHOR = re.compile(r"^(\d{1,3}(?:,\d{3})*\.\d{2})")

_KRW_SECTION = "원화 거래내역"
_USD_SECTION = "달러 거래내역"

# 헤더에서 데이터 행의 nums 토큰에 대응하지 않는 컬럼:
# - 거래일자/거래구분/종목명(종목코드)은 _DATA_LINE_RE 의 named group으로 잡힘
# - 환율은 KRW 거래 행에서 값이 비어 토큰으로 추출되지 않음
_HEADER_EXCLUDED = frozenset({"거래일자", "거래구분", "종목명(종목코드)", "환율"})
# USD 섹션은 환율 컬럼이 값으로 채워지므로(KRW 는 비어 있음) 환율을 제외하지 않는다.
# 또한 거래세 컬럼이 없다. KRW 제외셋을 재사용하면 전 컬럼이 한 칸씩 밀린다.
_USD_HEADER_EXCLUDED = frozenset({"거래일자", "거래구분", "종목명(종목코드)"})
_HEADER_REQUIRED = ("거래수량", "거래대금", "단가", "수수료")

# 헤더 라인이 보이지 않을 때 사용할 기본 컬럼 맵 (구 PDF 포맷, 정산금액 컬럼 없음)
_DEFAULT_COLUMN_MAP: dict[str, int] = {
    "거래수량": 0,
    "거래대금": 1,
    "단가": 2,
    "수수료": 3,
    "거래세": 4,
    "제세금": 5,
    "변제/연체합": 6,
    "잔고": 7,
    "잔액": 8,
}

# USD 섹션 기본 컬럼 맵. 헤더 '거래일자 거래구분 종목명(종목코드) 환율 거래수량 거래대금
# 정산금액 단가 수수료 제세금 변제/연체합 잔고 잔액' 기준 (환율 포함, 거래세 없음).
_USD_DEFAULT_COLUMN_MAP: dict[str, int] = {
    "환율": 0,
    "거래수량": 1,
    "거래대금": 2,
    "정산금액": 3,
    "단가": 4,
    "수수료": 5,
    "제세금": 6,
    "변제/연체합": 7,
    "잔고": 8,
    "잔액": 9,
}


def _parse_ticker_hint(raw_name: str) -> tuple[str, str | None]:
    """'삼성전자(A005930)' → ('삼성전자', '005930')"""
    m = _TICKER_RE.match(raw_name.strip())
    if m:
        return m.group(1).strip(), m.group(2)
    return raw_name.strip(), None


def _parse_usd_name(raw_name: str) -> str:
    """'팔란티어(US69608A1088)' → '팔란티어'. ISIN 은 hint 로 안 쓰므로 이름만 반환."""
    m = _USD_TICKER_RE.match(raw_name.strip())
    if m:
        return m.group(1).strip()
    return raw_name.strip()


def _parse_usd_isin(raw_name: str) -> str | None:
    """'팔란티어(US69608A1088)' → 'US69608A1088'. ISIN 없으면 None (종목명 폴백)."""
    m = _USD_TICKER_RE.match(raw_name.strip())
    return m.group(2) if m else None


def _split_usd_nums(rest: str) -> list[str]:
    """USD 데이터 행의 nums 토큰 리스트. 환율과 거래수량이 공백 없이 붙는 간헐 케이스
    ('1,370.300.004568')를 컬럼 인덱싱 전에 환율 앵커로 분리한다. 인덱싱 후 디-글루하면
    환율 이후 모든 컬럼 인덱스가 한 칸씩 밀린다.
    """
    rest = rest.strip()
    m = _USD_RATE_ANCHOR.match(rest)
    if not m:
        return rest.split()
    return [m.group(1), *rest[m.end():].split()]


def _build_column_map(
    header_line: str, excluded: frozenset[str] = _HEADER_EXCLUDED
) -> dict[str, int] | None:
    """헤더 라인 → {컬럼명: nums 인덱스} 매핑.

    토스가 컬럼 순서를 바꾸거나 추가(예: '정산금액')해도 동적으로 따라가도록 한다.
    필수 컬럼이 모두 없으면 헤더로 보기 어려워 None 반환 → 호출자는 fallback 사용.
    USD 섹션은 환율을 값으로 채우므로 `excluded=_USD_HEADER_EXCLUDED`(환율 미제외)로 호출한다.
    """
    tokens = header_line.split()
    if not all(name in tokens for name in _HEADER_REQUIRED):
        return None

    column_map: dict[str, int] = {}
    nums_idx = -1
    for token in tokens:
        if token in excluded:
            continue
        nums_idx += 1
        column_map[token] = nums_idx
    return column_map


class TossPdfParser(BrokerStatementParser):
    key = "toss_pdf"
    display_name = "토스증권"

    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        # pdfplumber.extract_tables() 는 토스 PDF 의 텍스트 레이아웃에서 테이블 경계를
        # 찾지 못해 빈 리스트만 반환한다. 따라서 페이지 텍스트를 줄 단위로 파싱한다.
        result = ParseResult()
        row_counter = 0
        column_map = _DEFAULT_COLUMN_MAP
        usd_column_map = _USD_DEFAULT_COLUMN_MAP

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

                    # 헤더 라인은 매 페이지 반복 노출된다. 토스가 컬럼을 추가(예: '정산금액')해도
                    # 데이터 행 인덱스가 밀리지 않도록 헤더에서 동적으로 매핑을 갱신한다.
                    if line.startswith("거래일자") and "단가" in line:
                        if in_usd:
                            new_map = _build_column_map(line, _USD_HEADER_EXCLUDED)
                            if new_map is not None:
                                usd_column_map = new_map
                        else:
                            new_map = _build_column_map(line)
                            if new_map is not None:
                                column_map = new_map
                        continue

                    if in_usd:
                        # USD 거래(구매/판매·ISIN)만 매칭. 환전/배당/이자 등 비거래 행은 제외.
                        if _USD_DATA_LINE_RE.match(line):
                            row_counter += 1
                            parsed = self._parse_usd_line(
                                line, row_counter, result, usd_column_map
                            )
                            if parsed:
                                result.trades.append(parsed)
                        continue
                    if not in_krw:
                        continue
                    if not _DATA_LINE_RE.match(line):
                        continue

                    row_counter += 1
                    parsed = self._parse_line(line, row_counter, result, column_map)
                    if parsed:
                        result.trades.append(parsed)

        return result

    def _parse_line(
        self,
        line: str,
        row_no: int,
        result: ParseResult,
        column_map: dict[str, int] | None = None,
    ) -> ParsedTrade | None:
        """텍스트 한 줄을 파싱하여 ParsedTrade 를 반환한다.

        `column_map` 은 헤더 라인에서 동적으로 추출한 {컬럼명: nums 인덱스} 매핑.
        미지정 시 구 PDF 포맷 (`_DEFAULT_COLUMN_MAP`) 으로 폴백한다. 토스가 컬럼을
        추가(예: '정산금액') 해도 헤더가 갱신되면 데이터 행 인덱스가 자동 보정된다.
        """
        m = _DATA_LINE_RE.match(line)
        if not m:
            return None

        date_raw = m.group("date")
        klass = m.group("klass")
        name_raw = m.group("name")
        nums = m.group("rest").split()
        cmap = column_map or _DEFAULT_COLUMN_MAP

        if klass == "구매":
            trade_type = TRADE_TYPE_BUY
        elif klass == "판매":
            trade_type = TRADE_TYPE_SELL
        else:
            result.add_error(row_no, f"알 수 없는 거래구분: {klass}")
            return None

        def _col(name: str) -> str:
            idx = cmap.get(name)
            if idx is None or idx >= len(nums):
                return ""
            return nums[idx]

        qty_raw = _col("거래수량")
        amount_raw = _col("거래대금")
        price_raw = _col("단가")
        fee_raw = _col("수수료")
        tax_raw = _col("거래세")
        sec_tax_raw = _col("제세금")

        if not qty_raw or not price_raw:
            result.add_error(
                row_no, f"필수 컬럼 누락 (qty={qty_raw!r}, price={price_raw!r}): {nums}"
            )
            return None

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

    def _parse_usd_line(
        self,
        line: str,
        row_no: int,
        result: ParseResult,
        column_map: dict[str, int] | None = None,
    ) -> ParsedTrade | None:
        """달러(USD) 섹션 한 줄을 파싱하여 USD 네이티브 ParsedTrade 를 반환한다.

        토스 달러 섹션의 모든 금액 컬럼은 원화 환산값이다. 환율(원/달러)로 나눠 USD 네이티브로
        복원한다 — price·commission·tax 세 필드 전부 ÷환율. `krw_normalized_trade` 가 셋을
        모두 ×exchange_rate 로 KRW 환원하므로 하나라도 KRW 로 남기면 원가가 ~환율배 부풀고
        `build_merge_patch` 비교가 깨진다.
        """
        m = _USD_DATA_LINE_RE.match(line)
        if not m:
            return None

        date_raw = m.group("date")
        klass = m.group("klass")
        name_raw = m.group("name")
        nums = _split_usd_nums(m.group("rest"))
        cmap = column_map or _USD_DEFAULT_COLUMN_MAP

        if klass == "구매":
            trade_type = TRADE_TYPE_BUY
        elif klass == "판매":
            trade_type = TRADE_TYPE_SELL
        else:
            result.add_error(row_no, f"알 수 없는 거래구분: {klass}")
            return None

        def _col(name: str) -> str:
            idx = cmap.get(name)
            if idx is None or idx >= len(nums):
                return ""
            return nums[idx]

        rate_raw = _col("환율")
        qty_raw = _col("거래수량")
        amount_raw = _col("거래대금")
        price_raw = _col("단가")
        fee_raw = _col("수수료")
        sec_tax_raw = _col("제세금")  # USD 섹션엔 거래세 컬럼이 없다.

        exchange_rate = parse_number(rate_raw)
        if exchange_rate <= 0:
            result.add_error(row_no, f"환율 누락/0 (rate={rate_raw!r}): {nums}")
            return None

        if not qty_raw or not price_raw:
            result.add_error(
                row_no, f"필수 컬럼 누락 (qty={qty_raw!r}, price={price_raw!r}): {nums}"
            )
            return None

        asset_name = _parse_usd_name(name_raw)
        if not asset_name:
            result.add_error(row_no, "종목명 없음")
            return None
        isin = _parse_usd_isin(name_raw)

        quantity = parse_number(qty_raw)
        amount_krw = parse_number(amount_raw)
        price_krw = parse_number(price_raw)
        commission_krw = parse_number(fee_raw)
        tax_krw = parse_number(sec_tax_raw)

        if quantity <= 0:
            result.add_error(row_no, f"수량({quantity})이 0 이하")
            return None

        if price_krw <= 0:
            price_krw = round(amount_krw / quantity, 4) if quantity > 0 else 0.0
        if price_krw <= 0:
            result.add_error(row_no, f"단가 계산 불가 (거래대금={amount_krw}, 수량={quantity})")
            return None

        # 원화 환산값 → USD 네이티브 복원 (세 필드 전부 ÷환율).
        price = price_krw / exchange_rate
        commission = commission_krw / exchange_rate
        tax = tax_krw / exchange_rate

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
            currency="USD",
            country_code="US",
            exchange_rate=exchange_rate,
            ticker_hint=None,  # ISIN 은 hint 로 쓰지 않는다 → isin 필드로 OpenFIGI 해소
            isin=isin,
            account_hint=result.account_hint,
            raw={"date": date_raw, "name": name_raw, "qty": qty_raw, "rate": rate_raw},
        )

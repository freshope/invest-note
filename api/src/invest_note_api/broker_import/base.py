"""증권사 파서 추상 기반 클래스 및 공통 데이터 타입."""

from __future__ import annotations

import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

import pdfplumber

from ..utils.numbers import strip_comma_number


def parse_number(s: object) -> float:
    """쉼표가 포함된 숫자 문자열을 float으로 변환한다. 변환 실패 시 0.0 반환."""
    if not s:
        return 0.0
    try:
        return float(str(strip_comma_number(s)))
    except ValueError:
        return 0.0


def extract_pdf_lines(
    file_bytes: bytes, account_re: re.Pattern[str]
) -> tuple[str | None, list[str]] | None:
    """PDF 바이트 → (account_hint, 비어있지 않은 줄 리스트).

    PDF 열기 실패(암호화 등) 시 None 을 반환한다 — 호출자는 사용자 친절 안내로 처리한다.
    PDF 파서(신한·미래에셋)가 공유하는 페이지 텍스트 수집 보일러플레이트.
    """
    try:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception:
        return None

    account_hint: str | None = None
    lines: list[str] = []
    with pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if account_hint is None:
                m = account_re.search(page_text)
                if m:
                    account_hint = m.group(1).strip()
            for line in page_text.split("\n"):
                line = line.strip()
                if line:
                    lines.append(line)
    return account_hint, lines


@dataclass
class ParsedTrade:
    source_row_no: int
    traded_at_kst: str          # "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS" (KST naive)
    trade_type: str             # "BUY" | "SELL"
    asset_name: str
    quantity: float
    price: float
    commission: float = 0.0
    tax: float = 0.0
    # 다운스트림 통화 권위는 country_code (currency_for_country): US=USD, 그 외=KRW.
    # currency 는 표시/디버그용 — country_code 와 drift 시 country_code 가 이긴다.
    currency: str = "KRW"
    country_code: str = "KR"
    exchange_rate: float = 1.0       # 원/달러 (해외 행만 1.0 != ); KR 행은 1.0
    ticker_hint: str | None = None   # 파일에서 직접 추출한 코드 (있을 때만, "이미 ticker")
    # ISIN 코드 (있을 때만, "조회 필요"). ticker_hint 와 의미 분리: ticker_hint 는 이미 ticker
    # (KR 6자리)라 권위로 쓰지만, isin 은 OpenFIGI 해소를 거쳐야 ticker 가 된다(둘을 섞으면
    # resolver 가 ISIN 을 code 로 오용). 토스 USD 행에서 추출.
    isin: str | None = None
    account_hint: str | None = None  # 파일 메타에서 추출한 계좌번호 문자열
    raw: dict = field(default_factory=dict)


@dataclass
class ParsedRow:
    """원장(import_ledger_entries) 캡처용 행 1건. 파일의 모든 데이터 행을 담는다.

    거래 인식 행(kind='trade')은 식별 필드 + dedup_key 를 채우고, 비거래/미인식 행
    (kind='non_trade'|'error')은 raw 만 담는다. raw 는 행 원문 전체 덤프(무손실 책임).
    분류(kind)는 파서의 best-effort 힌트일 뿐 — 물질화(Stage 2)에서 재해석한다.
    """

    source_row_no: int
    kind: str                        # "trade" | "non_trade" | "error"
    raw: dict
    traded_at_kst: str | None = None
    trade_type: str | None = None
    asset_name: str | None = None
    quantity: float | None = None
    price: float | None = None
    # 물질화(Stage 2)에 필요한 파서 산출 금액값 — tax 는 파서가 세목 합산(토스 거래세+제세금),
    # USD 는 ÷환율 변환값이라 원장 컬럼에 정규화해 둔다(원문 세목은 raw 에 보존).
    commission: float = 0.0
    tax: float = 0.0
    exchange_rate: float = 1.0
    currency: str = "KRW"
    country_code: str = "KR"
    ticker_hint: str | None = None
    isin: str | None = None
    dedup_key: str | None = None     # 거래 인식 행만 (비거래=None → 원장 dedup 대상 아님)


def _normalize_amount(value: object, places: int) -> str:
    quant = Decimal(1).scaleb(-places)
    return str(
        Decimal(str(value if value is not None else 0)).quantize(
            quant, rounding=ROUND_HALF_UP
        )
    )


def make_dedup_key(
    *,
    traded_at_kst: str | None,
    trade_type: str | None,
    asset_name: str | None,
    quantity: float | None,
    price: float | None,
    ticker_hint: str | None = None,
    country_code: str = "KR",
) -> str:
    """거래 행 dedup 키 — user-scope 원장 dedup 용 정규화 signature.

    Stage 2 trade-signature 와 동일 축(date+identifier+type+qty+price)에 country_code 를
    더해 KR/US 동명(同名) 충돌을 막는다. price 2자리·quantity 4자리(trades 컬럼 정밀도)로
    정규화해 포맷 차이를 흡수한다. identifier 는 ticker_hint 우선(없으면 asset_name).
    """
    date = (traded_at_kst or "")[:10]
    identifier = (ticker_hint or asset_name or "").strip()
    return "|".join(
        [
            date,
            country_code,
            identifier,
            trade_type or "",
            _normalize_amount(quantity, 4),
            _normalize_amount(price, 2),
        ]
    )


def row_from_trade(trade: "ParsedTrade", raw: dict | None = None) -> ParsedRow:
    """거래 인식 ParsedTrade → 원장 rows[] 용 ParsedRow(kind='trade', dedup_key 계산)."""
    return ParsedRow(
        source_row_no=trade.source_row_no,
        kind="trade",
        raw=raw if raw is not None else trade.raw,
        traded_at_kst=trade.traded_at_kst,
        trade_type=trade.trade_type,
        asset_name=trade.asset_name,
        quantity=trade.quantity,
        price=trade.price,
        commission=trade.commission,
        tax=trade.tax,
        exchange_rate=trade.exchange_rate,
        currency=trade.currency,
        country_code=trade.country_code,
        ticker_hint=trade.ticker_hint,
        isin=trade.isin,
        dedup_key=make_dedup_key(
            traded_at_kst=trade.traded_at_kst,
            trade_type=trade.trade_type,
            asset_name=trade.asset_name,
            quantity=trade.quantity,
            price=trade.price,
            ticker_hint=trade.ticker_hint,
            country_code=trade.country_code,
        ),
    )


@dataclass
class ParseResult:
    trades: list[ParsedTrade] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)   # {row_no, reason}
    account_hint: str | None = None
    usd_skip_count: int = 0
    # 원장 캡처용 — 파일의 모든 데이터 행(trade/non_trade/error). trades[]/errors[] 는
    # 기존 preview/commit 흐름(backward-compat)용, rows[] 는 Stage 1 원장 적재용.
    rows: list[ParsedRow] = field(default_factory=list)

    def add_error(self, row_no: int, reason: str, raw: dict | None = None) -> None:
        self.errors.append({"row_no": row_no, "reason": reason, "raw": raw or {}})

    def add_trade(self, trade: ParsedTrade, raw: dict | None = None) -> None:
        """거래 행을 backward-compat trades[] 와 원장 rows[] 양쪽에 등록.

        raw 를 주면 rows[] 엔트리의 원장 raw 로 사용(행 원문 전체 덤프). 안 주면 trade.raw.
        """
        self.trades.append(trade)
        self.rows.append(row_from_trade(trade, raw))

    def add_non_trade(
        self, source_row_no: int, raw: dict, kind: str = "non_trade"
    ) -> None:
        """비거래/미인식 행을 원장 rows[] 에만 등록(raw 전체 덤프, dedup_key 없음)."""
        self.rows.append(ParsedRow(source_row_no=source_row_no, kind=kind, raw=raw))


class BrokerStatementParser(ABC):
    key: str          # 레지스트리 식별자 (예: "samsung_xlsx")
    display_name: str # 사용자 노출 이름 (예: "삼성증권")
    # 파서 출력 shape 버전 — 원장 batch 에 기록해 drift 감지·재파싱 판단에 쓴다.
    # 파서 로직/추출 필드가 바뀌면 bump 한다.
    version: str = "1"

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        """파일 바이트를 받아 ParseResult 를 반환한다."""

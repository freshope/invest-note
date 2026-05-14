"""증권사 파서 추상 기반 클래스 및 공통 데이터 타입."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..utils.numbers import strip_comma_number


def parse_number(s: object) -> float:
    """쉼표가 포함된 숫자 문자열을 float으로 변환한다. 변환 실패 시 0.0 반환."""
    if not s:
        return 0.0
    try:
        return float(str(strip_comma_number(s)))
    except ValueError:
        return 0.0


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
    currency: str = "KRW"
    ticker_hint: str | None = None   # 파일에서 직접 추출한 코드 (있을 때만)
    account_hint: str | None = None  # 파일 메타에서 추출한 계좌번호 문자열
    raw: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    trades: list[ParsedTrade] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)   # {row_no, reason}
    account_hint: str | None = None
    usd_skip_count: int = 0

    def add_error(self, row_no: int, reason: str, raw: dict | None = None) -> None:
        self.errors.append({"row_no": row_no, "reason": reason, "raw": raw or {}})


class BrokerStatementParser(ABC):
    key: str          # 레지스트리 식별자 (예: "samsung_xlsx")
    display_name: str # 사용자 노출 이름 (예: "삼성증권")

    @classmethod
    @abstractmethod
    def match(cls, filename: str, head_bytes: bytes) -> bool:
        """파일명과 앞부분 바이트로 이 파서가 해당 파일을 처리할 수 있는지 판단."""

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        """파일 바이트를 받아 ParseResult 를 반환한다."""

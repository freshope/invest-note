"""증권사 파서 추상 기반 클래스 및 공통 데이터 타입."""

from __future__ import annotations

import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

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

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        """파일 바이트를 받아 ParseResult 를 반환한다."""

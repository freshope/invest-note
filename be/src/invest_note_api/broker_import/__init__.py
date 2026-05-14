"""증권사 파서 레지스트리 및 자동 감지."""

from __future__ import annotations

from .base import BrokerStatementParser, ParseResult
from .samsung_xlsx import SamsungXlsxParser
from .toss_pdf import TossPdfParser

# 새 증권사 파서 추가 시 여기에 인스턴스를 추가한다.
PARSERS: dict[str, BrokerStatementParser] = {
    SamsungXlsxParser.key: SamsungXlsxParser(),
    TossPdfParser.key: TossPdfParser(),
}

_HEAD_BYTES = 4096


def detect_broker(filename: str, file_bytes: bytes) -> str | None:
    """파일명과 앞부분 바이트를 이용해 증권사 키를 자동 감지한다.

    반환값: PARSERS 의 key 문자열, 감지 실패 시 None.
    """
    head = file_bytes[:_HEAD_BYTES]
    for key, parser in PARSERS.items():
        if parser.__class__.match(filename, head):
            return key
    return None


__all__ = ["PARSERS", "detect_broker", "BrokerStatementParser", "ParseResult"]

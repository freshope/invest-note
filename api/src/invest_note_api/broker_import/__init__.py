"""증권사 파서 레지스트리.

업로드 화면에서 사용자가 계좌(=증권사)를 직접 선택하므로 import 엔드포인트는 항상
`broker_key` 를 전달받는다. 파일명/바이트 기반 자동 감지는 불필요해 두지 않는다.
"""

from __future__ import annotations

from .base import BrokerStatementParser, ParseResult
from .samsung_xlsx import SamsungXlsxParser
from .toss_pdf import TossPdfParser

# 새 증권사 파서 추가 시 여기에 인스턴스를 추가한다.
PARSERS: dict[str, BrokerStatementParser] = {
    SamsungXlsxParser.key: SamsungXlsxParser(),
    TossPdfParser.key: TossPdfParser(),
}

__all__ = ["PARSERS", "BrokerStatementParser", "ParseResult"]

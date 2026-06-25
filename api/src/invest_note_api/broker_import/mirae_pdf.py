"""미래에셋증권 거래내역증명서 PDF 파서.

거래 1건 = 2줄(긴 ETF명은 줄바꿈으로 3줄):
  line1: <YYYY/MM/DD> (주식매수입고|주식매도출고) A<코드6> ... <거래금액>
  line2: <거래번호> <원번호> <수량> <단가> <종목명...> [<제세금합>] <유가잔고>

긴 ETF명은 종목명만 line2 에 오고 숫자 토큰은 line3 으로 밀린다. 이 경우 종목명은
line2(잘림 그대로), 숫자 토큰(seq/원번호/수량/단가/잔고)은 line3 에서 읽는다.

암호화 PDF(_1.pdf, AES /V4 /R4)는 pdfplumber 가 예외를 던지므로 잡아서 친절 안내한다.
주식 입출고(BUY/SELL) 외 현금leg(주식매수출금/매도입금)·이체·공모주·배당·예탁금이용료는 skip.
"""

from __future__ import annotations

import re

from invest_note_api.domain.trade_types import TRADE_TYPE_BUY, TRADE_TYPE_SELL

from .base import (
    BrokerStatementParser,
    ParsedTrade,
    ParseResult,
    extract_pdf_lines,
    parse_number,
)

_ACCOUNT_RE = re.compile(r"계좌번호\s+(\d{3}-\d{9})")
# line1 앵커: 날짜 + 주식매수입고|주식매도출고 + A코드(영숫자 6)
_LINE1_RE = re.compile(
    r"^(?P<date>\d{4}/\d{2}/\d{2})\s+"
    r"(?P<kind>주식매수입고|주식매도출고)\s+"
    r"A(?P<code>[0-9A-Z]{6})\b\s+(?P<rest>.+)$"
)
# line2/line3 의 데이터 토큰 시작: "<거래번호> <원번호> ..." → 첫 두 토큰이 숫자.
_DATA_HEAD_RE = re.compile(r"^\d+\s+\d+\s")
_NUM_RE = re.compile(r"^[\d,]+(?:\.\d+)?$")


class MiraePdfParser(BrokerStatementParser):
    key = "mirae_pdf"
    display_name = "미래에셋증권"

    def parse(self, file_bytes: bytes, filename: str) -> ParseResult:
        result = ParseResult()
        extracted = extract_pdf_lines(file_bytes, _ACCOUNT_RE)
        if extracted is None:
            # 암호화 PDF 등 열기 실패 — 빈 결과 대신 사용자 안내.
            result.add_error(
                0, "PDF 를 열 수 없습니다. 암호 없는 버전으로 재출력 후 업로드해 주세요."
            )
            return result
        result.account_hint, lines = extracted

        row_counter = 0
        for i, line in enumerate(lines):
            m1 = _LINE1_RE.match(line)
            if not m1:
                continue

            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if _DATA_HEAD_RE.match(next_line):
                # inline: line2 = "<seq> <orig> <qty> <price> <name...> [<tax>] <bal>"
                data_tokens = next_line.split()
                wrapped_name = None
            else:
                # wrapped: line2 = 종목명(잘림), 숫자 토큰 줄은 보통 line3.
                # 헤더/푸터가 한 줄 끼어 밀릴 수 있으므로 i+2..i+3 에서 데이터 줄을 전진 탐색.
                wrapped_name = next_line.strip()
                data_tokens = []
                for j in range(i + 2, min(i + 4, len(lines))):
                    if _DATA_HEAD_RE.match(lines[j]):
                        data_tokens = lines[j].split()
                        break

            row_counter += 1
            parsed = self._parse_record(
                m1, data_tokens, row_counter, result, wrapped_name=wrapped_name
            )
            if parsed:
                result.trades.append(parsed)

        return result

    def _parse_record(
        self,
        m1: re.Match,
        data_tokens: list[str],
        row_no: int,
        result: ParseResult,
        wrapped_name: str | None,
    ) -> ParsedTrade | None:
        # wrapped_name is None → inline(종목명이 data_tokens 에 포함), 아니면 줄바꿈된 종목명.
        inline = wrapped_name is None
        kind = m1.group("kind")
        trade_type = TRADE_TYPE_BUY if kind == "주식매수입고" else TRADE_TYPE_SELL

        # 거래금액 = line1 의 마지막 숫자 토큰 (수량 토큰이 끼는 행 대비).
        l1_rest = m1.group("rest").split()
        amount = next(
            (parse_number(t) for t in reversed(l1_rest) if _NUM_RE.match(t)), 0.0
        )

        # data_tokens: <seq> <orig> <qty> <price> [<name...>] [<tax>] <bal>
        if len(data_tokens) < 4:
            result.add_error(row_no, f"데이터 토큰 부족: {data_tokens}")
            return None
        quantity = parse_number(data_tokens[2])
        price = parse_number(data_tokens[3])

        trailing_tokens: list[str] = []
        if inline:
            # inline: 단가 뒤부터 종목명. 끝의 1~2 숫자 토큰(제세금합?/유가잔고)을 제외한다.
            # trailing 개수는 행마다 가변(유가잔고=0 이면 생략되어 1개)이라 거래유형으로 고정할 수
            # 없어 실제 숫자 토큰을 센다(최대 2). 종목명이 숫자로 끝나는 드문 경우 오인 가능 —
            # 단, 수량/단가/거래금액 정합은 선행 고정 위치라 영향 없음(known edge, 샘플엔 없음).
            tail = data_tokens[4:]
            num_trailing = 0
            for t in reversed(tail):
                if _NUM_RE.match(t):
                    num_trailing += 1
                else:
                    break
            num_trailing = min(num_trailing, 2)
            if num_trailing:
                name_tokens = tail[: len(tail) - num_trailing]
                trailing_tokens = tail[len(tail) - num_trailing :]
            else:
                name_tokens = tail
            asset_name = " ".join(name_tokens).strip()
        else:
            asset_name = (wrapped_name or "").strip()

        if not asset_name:
            result.add_error(row_no, "종목명 없음")
            return None

        if quantity <= 0 or price <= 0:
            result.add_error(row_no, f"수량({quantity}) 또는 단가({price})가 0 이하")
            return None

        # 정합성 가드: 수량 × 단가 == 거래금액.
        if amount and abs(quantity * price - amount) > 1.0:
            result.add_error(
                row_no,
                f"거래금액 불일치 (수량×단가={quantity * price}, 거래금액={amount})",
                {"name": asset_name},
            )
            return None

        # 매도 제세금합 = 종목명 뒤 첫 trailing 숫자(헤더 순서: 제세금합 입출금액 유가잔고).
        # 주식 매도행은 제세금합[ 유가잔고] 만 trailing 으로 남으므로 첫 토큰이 제세금합.
        # 줄바꿈(wrapped) 매도행은 제세금합이 line3 에 없어 0 으로 둔다(보수적).
        tax = 0.0
        if trade_type == TRADE_TYPE_SELL and inline and trailing_tokens:
            tax = parse_number(trailing_tokens[0])

        # 미래에셋 종목번호: 6자리 순수 숫자만 KRX 표준 코드로 신뢰(토스 파서와 동일 관례).
        # 'A0080G0' 같은 영숫자 사내 코드를 ticker 로 쓰면 같은 종목을 숫자 코드로 적재한
        # 다른 증권사 거래와 보유가 갈라지므로, 영숫자면 hint 를 비우고 종목명 매칭에 맡긴다.
        code = m1.group("code")
        ticker_hint = code if code.isdigit() else None

        return ParsedTrade(
            source_row_no=row_no,
            traded_at_kst=m1.group("date").replace("/", "-"),
            trade_type=trade_type,
            asset_name=asset_name,
            quantity=quantity,
            price=price,
            tax=tax,
            currency="KRW",
            ticker_hint=ticker_hint,
            account_hint=result.account_hint,
            raw={"date": m1.group("date"), "code": code},
        )

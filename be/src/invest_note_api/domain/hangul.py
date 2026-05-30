"""한글 초성 추출 — 종목 검색 초성 매칭용 (외부 의존 없음).

적재 시 `to_chosung` 으로 `name_chosung` / `alias_chosung` 컬럼을 채우고,
검색 시 `is_chosung_query` 로 입력이 전부 초성인지 판별해 초성 분기를 켠다.
"""
from __future__ import annotations

# 초성 인덱스(0~18) → 호환 자모(compatibility jamo). 사용자가 한글 키보드로 입력하는
# 자음과 동일한 코드포인트를 써서, 저장된 초성 문자열과 입력 초성이 정확히 일치하도록 한다.
_CHOSEONG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_CHOSEONG_SET = frozenset(_CHOSEONG)

_HANGUL_BASE = 0xAC00  # '가'
_HANGUL_LAST = 0xD7A3  # '힣'
_JONG_COUNT = 28
_JUNG_COUNT = 21


def to_chosung(text: str) -> str:
    """문자열의 한글 음절을 초성으로 치환한다. 한글 외 문자는 그대로 둔다.

    예: "삼성전자" → "ㅅㅅㅈㅈ", "TIGER 미국" → "TIGER ㅁㄱ".
    """
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if _HANGUL_BASE <= code <= _HANGUL_LAST:
            cho = (code - _HANGUL_BASE) // (_JONG_COUNT * _JUNG_COUNT)
            out.append(_CHOSEONG[cho])
        else:
            out.append(ch)
    return "".join(out)


def is_chosung_query(q: str) -> bool:
    """입력이 비어있지 않고 모든 문자가 초성 자모이면 True (초성 검색 분기 게이트)."""
    return bool(q) and all(ch in _CHOSEONG_SET for ch in q)

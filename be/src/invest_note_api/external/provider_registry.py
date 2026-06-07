"""외부 데이터 공급자 registry 공통 헬퍼.

각 도메인 모듈(quotes, stock_seed, daily_price_seed, nps_seed)은 자체
``dict[str, fn]`` registry 를 정의하고, env 에서 읽은 공급자 이름 체인을
이 헬퍼로 함수 리스트로 변환한다. 알 수 없는 이름은 ValueError —
서버(lifespan/라우터)와 배치(CLI main) 양 경로가 같은 코드패스로 검증된다.

config.py 는 도메인 모듈을 import 하지 않고 이름 문자열만 방출한다(순환 회피).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeVar

T = TypeVar("T")


def resolve_chain(names: Sequence[str], registry: Mapping[str, T], *, domain: str) -> list[T]:
    """공급자 이름 체인을 registry 의 구현 리스트로 변환. unknown 이름은 ValueError."""
    try:
        return [registry[n] for n in names]
    except KeyError as e:
        raise ValueError(
            f"{domain}: 알 수 없는 공급자 {e.args[0]!r} (등록: {sorted(registry)})"
        ) from None

"""응답 스키마 공통 베이스 — CamelModel + PnL 약어 보존 alias generator."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel as _pyd_to_camel


def to_camel_pnl(s: str) -> str:
    # `to_camel`은 `unrealized_pnl` → `unrealizedPnl`로 변환하지만 FE 타입은
    # `unrealizedPnL`(대문자 L) 컨벤션. 응답 필드명에 `_pnl` 접미사 외 `pnl`
    # 토큰이 없음을 확인한 뒤 1줄 wrapper로 치환한다.
    return _pyd_to_camel(s).replace("Pnl", "PnL")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel_pnl,
        populate_by_name=True,
        from_attributes=True,
    )

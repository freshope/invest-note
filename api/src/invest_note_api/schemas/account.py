from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, field_validator

_MAX_CASH = Decimal("9999999999999999.99")
_MAX_NAME = 50
_MAX_BROKER = 50


def _parse_cash(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value:
            return Decimal(0)
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("현금 잔액이 올바르지 않습니다.")
    if d < 0 or d > _MAX_CASH:
        raise ValueError("현금 잔액이 올바르지 않습니다.")
    return d


class AccountCreate(BaseModel):
    name: str
    broker: str | None = None
    cash_balance: Decimal = Decimal(0)

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("계좌 이름을 입력해주세요.")
        v = v.strip()
        if len(v) < 1:
            raise ValueError("계좌 이름을 입력해주세요.")
        if len(v) > _MAX_NAME:
            raise ValueError(f"계좌 이름은 {_MAX_NAME}자 이내여야 합니다.")
        return v

    @field_validator("broker", mode="before")
    @classmethod
    def _clean_broker(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("증권사 이름이 올바르지 않습니다.")
        v = v.strip()
        if not v:
            return None
        if len(v) > _MAX_BROKER:
            raise ValueError(f"증권사 이름은 {_MAX_BROKER}자 이내여야 합니다.")
        return v

    @field_validator("cash_balance", mode="before")
    @classmethod
    def _clean_cash(cls, v: object) -> Decimal:
        return _parse_cash(v)


class AccountUpdate(BaseModel):
    name: str | None = None
    broker: str | None = None
    cash_balance: Decimal | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("계좌 이름을 입력해주세요.")
        v = v.strip()
        if len(v) < 1:
            raise ValueError("계좌 이름을 입력해주세요.")
        if len(v) > _MAX_NAME:
            raise ValueError(f"계좌 이름은 {_MAX_NAME}자 이내여야 합니다.")
        return v

    @field_validator("broker", mode="before")
    @classmethod
    def _clean_broker(cls, v: object) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("증권사 이름이 올바르지 않습니다.")
        v = v.strip()
        if not v:
            return None
        if len(v) > _MAX_BROKER:
            raise ValueError(f"증권사 이름은 {_MAX_BROKER}자 이내여야 합니다.")
        return v

    @field_validator("cash_balance", mode="before")
    @classmethod
    def _clean_cash(cls, v: object) -> Decimal | None:
        if v is None:
            return None
        return _parse_cash(v)

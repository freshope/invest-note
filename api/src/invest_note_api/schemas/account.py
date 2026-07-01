from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, field_validator

from ..utils.numbers import strip_comma_number

_MAX_CASH = Decimal("9999999999999999.99")
_MAX_NAME = 50
_MAX_BROKER = 50
_MAX_ACCOUNT_NUMBER = 64


def _parse_cash(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    value = strip_comma_number(value)
    if isinstance(value, str) and not value:
        return Decimal(0)
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("현금 잔액이 올바르지 않습니다.")
    if d < 0 or d > _MAX_CASH:
        raise ValueError("현금 잔액이 올바르지 않습니다.")
    return d


def _parse_name(v: object) -> str:
    if not isinstance(v, str):
        raise ValueError("계좌 이름을 입력해주세요.")
    v = v.strip()
    if len(v) < 1:
        raise ValueError("계좌 이름을 입력해주세요.")
    if len(v) > _MAX_NAME:
        raise ValueError(f"계좌 이름은 {_MAX_NAME}자 이내여야 합니다.")
    return v


def _parse_broker(v: object) -> str | None:
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


def _parse_account_number(v: object) -> str | None:
    # 저장은 raw(파싱 원문) — 숫자만 강제하지 않는다. 정규화/동일성 비교는 FE 매칭 시점.
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("계좌번호가 올바르지 않습니다.")
    v = v.strip()
    if not v:
        return None
    if len(v) > _MAX_ACCOUNT_NUMBER:
        raise ValueError(f"계좌번호는 {_MAX_ACCOUNT_NUMBER}자 이내여야 합니다.")
    return v


class AccountCreate(BaseModel):
    name: str
    broker: str | None = None
    cash_balance: Decimal = Decimal(0)
    account_number: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: object) -> str:
        return _parse_name(v)

    @field_validator("broker", mode="before")
    @classmethod
    def _clean_broker(cls, v: object) -> str | None:
        return _parse_broker(v)

    @field_validator("cash_balance", mode="before")
    @classmethod
    def _clean_cash(cls, v: object) -> Decimal:
        return _parse_cash(v)

    @field_validator("account_number", mode="before")
    @classmethod
    def _clean_account_number(cls, v: object) -> str | None:
        return _parse_account_number(v)


class AccountUpdate(BaseModel):
    name: str | None = None
    broker: str | None = None
    cash_balance: Decimal | None = None
    account_number: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: object) -> str | None:
        return None if v is None else _parse_name(v)

    @field_validator("broker", mode="before")
    @classmethod
    def _clean_broker(cls, v: object) -> str | None:
        return _parse_broker(v)

    @field_validator("cash_balance", mode="before")
    @classmethod
    def _clean_cash(cls, v: object) -> Decimal | None:
        return None if v is None else _parse_cash(v)

    @field_validator("account_number", mode="before")
    @classmethod
    def _clean_account_number(cls, v: object) -> str | None:
        return _parse_account_number(v)

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

ERR_TRADE_NOT_FOUND = "거래를 찾을 수 없습니다."
ERR_ACCOUNT_NOT_FOUND = "계좌를 찾을 수 없습니다."
ERR_UNAUTHORIZED = "Unauthorized"
ERR_FORBIDDEN = "Forbidden"
ERR_REQUEST_FALLBACK = "올바르지 않은 요청입니다."
ERR_LOCK_BUSY = "처리 중 다른 요청과 충돌이 발생했습니다. 잠시 후 다시 시도해주세요."


class APIError(Exception):
    def __init__(self, message: str, status: int) -> None:
        self.message = message
        self.status = status
        super().__init__(message)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    msg = first.get("msg", ERR_REQUEST_FALLBACK)
    return JSONResponse(status_code=422, content={"error": msg})

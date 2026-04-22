from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError


class APIError(Exception):
    def __init__(self, message: str, status: int) -> None:
        self.message = message
        self.status = status
        super().__init__(message)


def validate_body[T: BaseModel](model_cls: type[T], body: dict) -> T:
    try:
        return model_cls.model_validate(body)
    except ValidationError as e:
        first = e.errors()[0]
        raise APIError(first.get("msg", "올바르지 않은 입력입니다."), 400)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    msg = first.get("msg", "올바르지 않은 요청입니다.")
    return JSONResponse(status_code=422, content={"error": msg})

from fastapi import Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, message: str, status: int) -> None:
        self.message = message
        self.status = status
        super().__init__(message)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.message})

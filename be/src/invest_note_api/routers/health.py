from fastapi import APIRouter

router = APIRouter()


@router.api_route("/healthz", methods=["GET", "HEAD"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

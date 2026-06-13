from fastapi import APIRouter

router = APIRouter()


# 인프라 헬스체크 — OpenAPI 문서에 노출 불필요. GET·HEAD 한 라우트로 묶으면 두 메서드가
# 같은 operation_id 를 공유해 "Duplicate Operation ID" 경고가 나므로 스키마에서 제외한다.
@router.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

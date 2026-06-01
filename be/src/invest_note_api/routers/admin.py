"""관리자 트리거 라우터 — 종목 마스터 적재를 백그라운드로 시작."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from invest_note_api.auth.admin import require_admin_token
from invest_note_api.config import Settings, get_settings
from invest_note_api.services.stock_seed import seed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


async def run_seed(db_url: str, api_key: str) -> None:
    """백그라운드 적재 래퍼 — CLI 와 동일하게 seed()가 자체 asyncpg.connect 로 동작.

    풀(Depends(get_pool)) 을 쓰지 않는다 — seed 가 session advisory lock 을 수 분 보유하므로
    요청 풀을 차용하면 풀 고갈·lock leak 이 발생한다. 실패가 silent 로 묻히지 않게 로깅한다.
    """
    try:
        await seed(db_url, api_key=api_key)
    except Exception:
        logger.exception("admin seed/stocks 백그라운드 실행 실패")


@router.post("/seed/stocks", status_code=202)
async def trigger_seed_stocks(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_token),
    settings: Settings = Depends(get_settings),
) -> dict:
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    background_tasks.add_task(run_seed, db_url, settings.data_go_kr_api_key)
    return {"status": "started"}

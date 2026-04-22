from fastapi import APIRouter, Depends

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser

router = APIRouter()


@router.get("/me")
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    return {"user_id": str(user.id), "email": user.email}

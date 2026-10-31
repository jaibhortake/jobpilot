from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.deps import db_ok

router = APIRouter()


@router.get("/health")
async def health(ok: Annotated[bool, Depends(db_ok)]) -> dict[str, str | bool]:
    return {"status": "ok", "db": ok}

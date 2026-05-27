from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    summary="Health check",
    tags=["health"],
    responses={200: {"content": {"application/json": {"example": {"status": "ok"}}}}},
)
def health_check() -> dict:
    return {"status": "ok"}

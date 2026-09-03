from fastapi import APIRouter


router = APIRouter(
    prefix="/api-users",
    tags=["Пользователи"],
)

@router.get("/")
async def user():
    return {"message": "user"}
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.users import User

from app.security import decode_access_token



oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api-users/login"
)


async def get_current_api_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session)
):
    user_id = decode_access_token(token)

    result = await session.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Пользователь не найден",
        )

    return user
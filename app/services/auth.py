import jwt

from fastapi import Depends, HTTPException, Cookie
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.users import User

from app.security import decode_access_token, SECRET_KEY, ALGORITHM



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


async def get_current_web_user(
    access_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session)
):
    if access_token is None:
        return None
    
    try:
        payload = jwt.decode(
            access_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            return None

    except jwt.InvalidTokenError:
        return None

    user = await session.get(User, int(user_id))

    if user is None:
        return None

    return user
from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile

from pydantic import ValidationError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models.users import User

from app.security import hash_password
from app.schemas.users import UserCreate, UserResponse
from app.services.files import upload_image, delete_image


router = APIRouter(
    prefix="/api-users",
    tags=["Пользователи"],
)

@router.post("/register", response_model=UserResponse)
async def register_user(
    username: str = Form(...),
    name: str | None = Form(default=None),
    email: str = Form(...),
    password: str = Form(...),
    image: UploadFile | None = None,
    session: AsyncSession = Depends(get_session)
):
    image_name = None
    user_id = None

    try:
        user = UserCreate(
            username=username,
            name=name,
            email=email,
            password=password
        )


        statement_username = select(User).where(
            User.username == user.username
        )

        existing_username = await session.scalar(statement_username)

        if existing_username is not None:
            raise HTTPException(
                status_code=400,
                detail="Пользователь с таким именем уже существует"
            )

        statement_email = select(User).where(
            User.email == user.email
        )

        existing_email = await session.scalar(statement_email)

        if existing_email is not None:
            raise HTTPException(
                status_code=400,
                detail="Пользователь с таким email уже существует"
            )

        password_hash = hash_password(user.password)

        new_user = User(
            username=user.username,
            name=user.name,
            email=user.email,
            password_hash=password_hash
        )
        
        session.add(new_user)
        await session.flush()

        user_id = new_user.id

        if image:
            image_name = await upload_image(image, user_id)
            new_user.photo = image_name

        await session.commit()
        await session.refresh(new_user)

        return new_user

    except ValidationError:
        raise HTTPException(
            status_code=400,
            detail="Неправильный формат"
        )

    except Exception:
        await session.rollback()

        if image_name and user_id:
            delete_image(image_name, user_id)

        raise
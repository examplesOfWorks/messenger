from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile
from fastapi.security import OAuth2PasswordRequestForm

from pydantic import ValidationError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import get_session
from db.models.users import User, Friendship

from app.security import hash_password, verify_password, create_access_token
from app.schemas.users import UserCreate, UserResponse, TokenResponse
from app.services.files import upload_image, delete_image
from app.services.auth import get_current_api_user

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


@router.post(
    "/login",
    response_model=TokenResponse
)
async def login(
    user: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(User).where(User.username == user.username)
    )

    existing_user = result.scalar_one_or_none()

    if existing_user is None:
        raise HTTPException(
            status_code=401,
            detail="Неверное имя пользователя или пароль"
        )

    if not verify_password(
        user.password,
        existing_user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Неверное имя пользователя или пароль"
        )

    access_token = create_access_token(existing_user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/profile", response_model=UserResponse)
@router.get("/profile/{user_id}", response_model=UserResponse)
async def profile(
    user_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):
    if user_id is None:
        return current_user

    user = await session.get(User, user_id)

    if user is None:
        raise HTTPException(
        status_code=404,
        detail="Пользователь не найден"
    )

    return user


@router.get("/users", response_model=list[UserResponse])
async def users_list(
    session: AsyncSession = Depends(get_session)
):

    result = await session.execute(select(User))
    users = result.scalars().all()

    return users


@router.get("/friend-requests/incoming")
async def incoming_friend_requests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):
    result = await session.execute(
        select(Friendship)
        .options(
            selectinload(Friendship.requester)
        )
        .where(
            (Friendship.addressee_id == current_user.id)
        )
    )

    requests = result.scalars().all()

    return requests


@router.get("/friend-requests/outgoing")
async def outgoing_friend_requests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):
    result = await session.execute(
        select(Friendship)
        .options(
            selectinload(Friendship.addressee)
        )
        .where(
            (Friendship.requester_id == current_user.id)
        )
    )

    requests = result.scalars().all()

    return requests
    

@router.post("/friend-request/{user_id}")
async def friend_request(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя добавить самого себя в друзья"
        )

    target_user = await session.get(User, user_id)

    if target_user is None:
        raise HTTPException(
        status_code=404,
        detail="Пользователь не найден"
    )

    result = await session.execute(
        select(Friendship).where(
            (
                (Friendship.requester_id == current_user.id)
                & (Friendship.addressee_id == user_id)
            ) |
            (
                (Friendship.requester_id == user_id)
                & (Friendship.addressee_id == current_user.id)
            )
        )
    )

    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400,
            detail="Отношение между пользователями уже существует"
        )

    friendship = Friendship(
        requester_id=current_user.id,
        addressee_id=user_id
    )

    session.add(friendship)

    try:
        await session.commit()

    except IntegrityError:
        await session.rollback()

        raise HTTPException(
            status_code=400,
            detail="Отношение между пользователями уже существует",
        )

    await session.refresh(friendship)

    return friendship


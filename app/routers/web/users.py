from fastapi import APIRouter, Request, Form, UploadFile, Depends, File, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from pydantic import ValidationError

from db.database import get_session
from db.models.users import User, Friendship

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.users import UserCreate
from app.security import hash_password, verify_password, create_access_token
from app.services.files import upload_image, delete_image
from app.services.auth import get_current_web_user


templates = Jinja2Templates(directory="templates")


router = APIRouter(
    prefix="/users"
)


@router.get("/register", include_in_schema=False)
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="/users/register.html"
    )


@router.post("/register", include_in_schema=False)
async def register_user(
    request: Request,
    username: str = Form(...),
    name: str | None = Form(default=None),
    email: str = Form(...),
    password: str = Form(...),
    image: UploadFile | None = File(default=None),
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
            return templates.TemplateResponse(
                request=request,
                name="users/register.html",
                context={
                    "error": "Пользователь с таким именем уже существует",
                    "username": username,
                    "name": name,
                    "email": email
                },
                status_code=400
            )

        statement_email = select(User).where(
            User.email == user.email
        )

        existing_email = await session.scalar(statement_email)

        if existing_email is not None:
            return templates.TemplateResponse(
                request=request,
                name="users/register.html",
                context={
                    "error": "Пользователь с таким email уже существует",
                    "username": username,
                    "name": name,
                    "email": email
                },
                status_code=400
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

        return RedirectResponse(
            url="/users/login",
            status_code=302
        )

    except ValidationError:
        return templates.TemplateResponse(
                request=request,
                name="users/register.html",
                context={
                    "error": "Неправильный формат",
                    "username": username,
                    "name": name,
                    "email": email
                },
                status_code=400
            )

    except Exception:
        await session.rollback()

        if image_name and user_id:
            delete_image(image_name, user_id)

        raise

@router.get("/login", include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="/users/login.html"
    )


@router.post("/login", include_in_schema=False)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(User).where(User.username == username)
    )

    existing_user = result.scalar_one_or_none()

    if existing_user is None:
        return templates.TemplateResponse(
            request=request,
            name="users/login.html",
            context={
                "error": "Неверное имя пользователя или пароль",
                "username": username,
            },
            status_code=401
        )

    if not verify_password(
        password,
        existing_user.password_hash
    ):
        return templates.TemplateResponse(
            request=request,
            name="users/login.html",
            context={
                "error": "Неверное имя пользователя или пароль",
                "username": username,
            },
            status_code=401
        )

    access_token = create_access_token(existing_user.id)

    response = RedirectResponse(
        url="/users/profile",
        status_code=303
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True
    )

    return response


@router.get("/profile", include_in_schema=False)
@router.get("/profile/{user_id}", include_in_schema=False)
async def profile(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: int | None = None,
    current_user: User = Depends(get_current_web_user),
    success: str | None = Query(default=None),
    error: str | None = Query(default=None)
):

    if not current_user:
        return RedirectResponse(
            url="/users/login",
            status_code=303
        )

    if user_id is None:
        user = current_user
    else:
        user = await session.get(User, user_id)

    if user is None:
        raise HTTPException(
        status_code=404,
        detail="Пользователь не найден"
    )

    friendship = None
    friendship_status = ""

    if user.id != current_user.id:
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

        friendship = result.scalar_one_or_none()

        if friendship is not None:
            print(friendship.status, friendship.requester_id == current_user.id)
            if friendship.status == "pending" and friendship.requester_id == current_user.id:
                friendship_status = "outgoing"
            elif friendship.status == "pending" and friendship.addressee_id == current_user.id:
                friendship_status = "incoming"

    return templates.TemplateResponse(
        request=request,
        name="users/profile.html",
        context={
            "current_user": current_user,
            "user": user,
            "success": success,
            "error": error,
            "friendship_status": friendship_status
        }
    )


@router.get("/users-list", include_in_schema=False)
async def users_list(
    request: Request,
    current_user: User = Depends(get_current_web_user),
    session: AsyncSession = Depends(get_session)
):

    result = await session.execute(select(User))
    users = result.scalars().all()

    return templates.TemplateResponse(
            request=request,
            name="users/users.html",
            context={
                "users": users,
                "current_user": current_user
            }
        )


@router.post("/friend-request/{user_id}", include_in_schema=False)
async def friend_request(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
):

    if user_id == current_user.id:
        return RedirectResponse(
            url=f"/users/profile/{user_id}?error=Нельзя добавить самого себя",
            status_code=303,
        )

    target_user = await session.get(User, user_id)

    if target_user is None:
        return RedirectResponse(
            url="/users?error=Пользователь не найден",
            status_code=303,
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
        return RedirectResponse(
            url=f"/users/profile/{user_id}?error=Заявка уже была отправлена",
            status_code=303,
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

        return RedirectResponse(
            url=f"/users/profile/{user_id}?error=Не удалось отправить заявку",
            status_code=303,
        )

    await session.refresh(friendship)

    return RedirectResponse(
        url=f"/users/profile/{user_id}?success=Заявка отправлена",
        status_code=303,
    )



@router.get("/logout", include_in_schema=False)
def logout_user():
    response = RedirectResponse(
        url="/users/login",
        status_code=303
    )

    response.delete_cookie("access_token")

    return response
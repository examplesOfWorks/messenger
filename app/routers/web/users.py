from fastapi import APIRouter, Request, Form, UploadFile, Depends, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from pydantic import ValidationError

from db.database import get_session
from db.models.users import User

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.users import UserCreate
from app.security import hash_password
from app.services.files import upload_image, delete_image


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
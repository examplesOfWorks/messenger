import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from db.database import AsyncSessionLocal

from app.routers.api.users import router as users_api_router
from app.routers.web.users import router as users_web_router

from app.routers.api.friendships import router as friendships_api_router
from app.routers.web.friendships import router as friendships_web_router

from app.routers.api.messenger import router as messenger_api_router
from app.routers.web.messenger import router as messenger_web_router

from app.routers.web.websocket import router as websocket_router

from app.services.auth import get_current_web_user



app = FastAPI()

templates = Jinja2Templates(directory="templates")



# api
app.include_router(users_api_router)
app.include_router(friendships_api_router)
app.include_router(messenger_api_router)

# web
app.include_router(users_web_router)
app.include_router(friendships_web_router)
app.include_router(messenger_web_router)

app.include_router(websocket_router)


app.mount(
    "/media",
    StaticFiles(directory="media"),
    name="media",
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


@app.get("/", include_in_schema=False)
async def home():
    return RedirectResponse(
        url="/users/profile",
        status_code=303,
    )


@app.exception_handler(403)
async def forbidden_page(request: Request, exc):
    if "api" in request.url.path:
        return JSONResponse(
            status_code=403,
            content={"detail": exc.detail}
        )
    
    async with AsyncSessionLocal() as session:
        current_user = await get_current_web_user(
            access_token=request.cookies.get("access_token"),
            session=session,
        )
    
    return templates.TemplateResponse(
        request=request,
        name="errors/403.html",
        status_code=403,
        context={
            "request": request,
            "detail": exc.detail if exc.detail != "Forbidden" else "",
            "current_user": current_user
        }
    )


@app.exception_handler(404)
async def not_found_page(request: Request, exc):
    if "api" in request.url.path:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.detail}
        )
    
    async with AsyncSessionLocal() as session:
        current_user = await get_current_web_user(
            access_token=request.cookies.get("access_token"),
            session=session,
        )
    
    return templates.TemplateResponse(
        request=request,
        name="errors/404.html",
        status_code=404,
        context={
            "request": request,
            "detail": exc.detail if exc.detail != "Not Found" else "",
            "current_user": current_user
        }
    )



if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

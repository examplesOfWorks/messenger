import uvicorn

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.routers.api.users import router as users_api_router

from app.routers.web.users import router as users_web_router

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# api
app.include_router(users_api_router)

# web
app.include_router(users_web_router)

app.mount(
    "/media",
    StaticFiles(directory="media"),
    name="media",
)

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

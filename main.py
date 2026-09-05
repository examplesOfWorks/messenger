import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from db.database import engine

from sqlalchemy.orm import Session

from app.routers.api.users import router as users_api_router
from app.routers.web.users import router as users_web_router
from app.services.auth import get_current_web_user


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

@app.exception_handler(404)
def not_found_page(request: Request, exc):
    if "api" in request.url.path:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.detail}
        )
    
    with Session(engine) as session:
        current_user = get_current_web_user(
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

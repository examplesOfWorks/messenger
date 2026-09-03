import uvicorn

from fastapi import FastAPI

from app.routers.api.users import router as users_api_router


app = FastAPI()


app.include_router(users_api_router)



if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

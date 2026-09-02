import uvicorn

from fastapi import FastAPI, Depends

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session


app = FastAPI()


@app.get("/")
async def db_check(
    session: AsyncSession = Depends(get_session)
):
    try:
        value = await session.execute(text("SELECT 1"))
        result = value.scalar_one()

        return {"database": result}

    except Exception as e:
        return {"message": "Connection failed", "error": str(e)}, 500



if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

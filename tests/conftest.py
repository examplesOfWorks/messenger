import os

import pytest_asyncio
from dotenv import load_dotenv

from fastapi import WebSocketDisconnect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from main import app
from app.services.auth import get_current_api_user, get_current_web_user

from db.database import get_session
from db.models.base import Base
from db.models.users import User

from httpx import ASGITransport, AsyncClient



load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

class FakeWebSocket:

    def __init__(self, incoming_messages=None):
        self.accepted = False
        self.sent_messages = []
        self.incoming_messages = list(incoming_messages or [])

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.sent_messages.append(data)

    async def receive_json(self):
        if self.incoming_messages:
            return self.incoming_messages.pop(0)

        raise WebSocketDisconnect()


class BrokenFakeWebSocket(FakeWebSocket):
    async def send_json(self, data):
        raise RuntimeError("WebSocket connection is broken")
    

@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    async with SessionLocal() as session:
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()



@pytest_asyncio.fixture
async def user(session):
    user = User(
        username="test_user",
        email="test@example.com",
        password_hash="test_hash",
    )
    session.add(user)
    await session.flush()

    return user


@pytest_asyncio.fixture
async def second_user(session):
    user = User(
        username="second_user",
        email="second@example.com",
        password_hash="test_hash",
    )
    session.add(user)
    await session.flush()

    return user


@pytest_asyncio.fixture
async def client(session, user):
    original_overrides = app.dependency_overrides.copy()

    async def override_get_session():
        yield session

    async def override_get_current_api_user():
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_api_user] = (
        override_get_current_api_user
    )

    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


@pytest_asyncio.fixture
async def web_client(session, user):
    original_overrides = app.dependency_overrides.copy()

    async def override_get_session():
        yield session

    async def override_get_current_web_user():
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_web_user] = (
        override_get_current_web_user
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

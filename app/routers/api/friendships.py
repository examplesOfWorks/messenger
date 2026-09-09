from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import get_session
from db.models.users import User
from db.models.friendships import Friendship

from app.schemas.friendships import FriendRequestResponse, FriendResponse
from app.services.auth import get_current_api_user

from datetime import datetime, timezone

import itertools


router = APIRouter(
    prefix="/api-friendships",
    tags=["Друзья"],
)


@router.get("/friends", response_model=list[FriendResponse])
async def users_friends(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user),
):
    requester_result = await session.execute(
        select(Friendship)
        .options(
            selectinload(Friendship.addressee)
        )
        .where(
            Friendship.requester_id == current_user.id,
            Friendship.status == "accepted"
        )
    )

    addressee_result = await session.execute(
        select(Friendship)
        .options(
            selectinload(Friendship.requester)
        )
        .where(
            Friendship.addressee_id == current_user.id,
            Friendship.status == "accepted"
        )
    )

    requester_friendships = requester_result.scalars().all()
    addressee_friendships = addressee_result.scalars().all()

    friendships = list(itertools.chain(requester_friendships, addressee_friendships))

    friendships.sort(key=lambda friendship: friendship.accepted_at, reverse=True)

    friends = []

    for friendship in friendships:
        if friendship.requester_id == current_user.id:
            friend = friendship.addressee
        else:
            friend= friendship.requester

        friends.append(
            FriendResponse(
                accepted_at=friendship.accepted_at,
                friend=friend,
            )
        )

    return friends


@router.get("/friend-requests/incoming", response_model=list[FriendRequestResponse])
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
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        )
    )

    requests = result.scalars().all()

    return requests


@router.get("/friend-requests/outgoing", response_model=list[FriendRequestResponse])
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
            Friendship.requester_id == current_user.id,
            Friendship.status == "pending"
        )
    )

    requests = result.scalars().all()

    return requests
  

@router.post("/friend-requests/{user_id}")
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


@router.post("/friend-requests/{friendship_id}/accept")
async def accept_friendship(
    friendship_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):

    friendship = await session.scalar(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        )
    )


    if friendship is None:
        raise HTTPException(
        status_code=404,
        detail="Заявка не найдена"
    )
 
    friendship.status = "accepted"
    friendship.accepted_at = datetime.now(timezone.utc)

    await session.commit()

    return friendship


@router.delete("/friend-requests/{friendship_id}/reject")
async def reject_friendship(
    friendship_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):

    friendship = await session.scalar(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        )
    )

    if friendship is None:
        raise HTTPException(
        status_code=404,
        detail="Заявка не найдена"
    )

    await session.delete(friendship)
    await session.commit()

    return {"message": "Вы отклонили заявку"}


@router.delete("/friend-requests/{friendship_id}/cancel")
async def cancel_friendship(
    friendship_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_api_user)
):
    friendship = await session.scalar(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.requester_id == current_user.id,
            Friendship.status == "pending"
        )
    )

    if friendship is None:
        raise HTTPException(
        status_code=404,
        detail="Заявка не найдена"
    )

    await session.delete(friendship)
    await session.commit()

    return {"message": "Вы отменили заявку"}
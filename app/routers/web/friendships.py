from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.database import get_session
from db.models.users import User
from db.models.friendships import Friendship

from app.schemas.friendships import FriendResponse
from app.services.auth import get_current_web_user
from app.services.friendships import get_friend_request_counts

from datetime import datetime, timezone

import itertools



templates = Jinja2Templates(directory="templates")

router = APIRouter(
    prefix="/friendships"
)



@router.get("/friends", include_in_schema=False)
async def users_friends(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user),
):

    if not current_user:
        return RedirectResponse(
            url="/users/login",
            status_code=303
        )

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

    return templates.TemplateResponse(
        request=request,
        name="friendships/friends.html",
        context={
            "current_user": current_user,
            "friends": friends
        }
    )


@router.get("/friend-requests/incoming", include_in_schema=False)
async def incoming_friend_requests(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
):
    if not current_user:
        return RedirectResponse(
            url="/users/login",
            status_code=303
        )

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

    incoming_count, outgoing_count = await get_friend_request_counts(session, current_user.id)
    
    return templates.TemplateResponse(
        request=request,
        name="friendships/friend_requests.html",
        context={
            "current_user": current_user,
            "requests": requests,
            "request_type": "incoming",
            "incoming_count": incoming_count,
            "outgoing_count": outgoing_count
        },
    )


@router.get("/friend-requests/outgoing", include_in_schema=False)
async def outgoing_friend_requests(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
):
    if not current_user:
        return RedirectResponse(
            url="/users/login",
            status_code=303
        )

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

    incoming_count, outgoing_count = await get_friend_request_counts(session, current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="friendships/friend_requests.html",
        context={
            "current_user": current_user,
            "requests": requests,
            "request_type": "outgoing",
            "incoming_count": incoming_count,
            "outgoing_count": outgoing_count
        },
    )


@router.post("/friend-requests/{user_id}", include_in_schema=False)
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


@router.post("/friend-requests/{friendship_id}/accept", include_in_schema=False)
async def accept_friendship(
    friendship_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
):

    friendship = await session.scalar(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        )
    )

    if friendship is None:
        return RedirectResponse(
        url=f"/friendships/friend-requests/incoming?error=Заявка не найдена",
        status_code=303,
    )
 
    friendship.status = "accepted"
    friendship.accepted_at = datetime.now(timezone.utc)

    await session.commit()

    return RedirectResponse(
        url=f"/friendships/friend-requests/incoming?success=Заявка принята",
        status_code=303,
    )


@router.post("/friend-requests/{friendship_id}/reject", include_in_schema=False)
async def reject_friendship(
    friendship_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
):

    friendship = await session.scalar(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == "pending"
        )
    )

    if friendship is None:
        return RedirectResponse(
        url=f"/friendships/friend-requests/incoming?error=Заявка не найдена",
        status_code=303,
    )

    await session.delete(friendship)
    await session.commit()

    return RedirectResponse(
        url=f"/friendships/friend-requests/incoming?success=Вы отклонили заявку",
        status_code=303,
    )


@router.post("/friend-requests/{friendship_id}/cancel", include_in_schema=False)
async def cancel_friendship(
    friendship_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_web_user)
):

    friendship = await session.scalar(
        select(Friendship).where(
            Friendship.id == friendship_id,
            Friendship.requester_id == current_user.id,
            Friendship.status == "pending"
        )
    )

    if friendship is None:
        return RedirectResponse(
            url=f"/friendships/friend-requests/outgoing?error=Заявка не найдена",
            status_code=303,
        )

    await session.delete(friendship)
    await session.commit()

    return RedirectResponse(
        url=f"/friendships/friend-requests/outgoing?success=Вы отменили заявку",
        status_code=303,
    )

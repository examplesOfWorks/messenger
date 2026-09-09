from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.friendships import Friendship


async def get_friend_request_counts(
    session: AsyncSession,
    user_id: int
): 
    incoming_count = await session.scalar(
        select(func.count(Friendship.id)).where(
            Friendship.addressee_id == user_id,
            Friendship.status == "pending",
        )
    )

    outgoing_count = await session.scalar(
        select(func.count(Friendship.id)).where(
            Friendship.requester_id == user_id,
            Friendship.status == "pending",
        )
    )

    return incoming_count or 0, outgoing_count or 0
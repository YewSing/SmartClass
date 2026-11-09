from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.class_ import ClassOccurrence
from app.models.user import Lecturer, User

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not user_id or token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


def require_role(*roles: str):
    """Factory returning a dependency that enforces role membership."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return _check


async def ensure_teaches_occurrence(db: AsyncSession, actor: User, occurrence_id: int) -> Lecturer:
    """NFR-04: 403 unless `actor` is the lecturer assigned to this class. Returns their Lecturer row."""
    lecturer = (await db.execute(select(Lecturer).where(Lecturer.user_id == actor.id))).scalar_one_or_none()
    assigned_id = await db.scalar(select(ClassOccurrence.lecturer_id).where(ClassOccurrence.id == occurrence_id))
    if lecturer is None or assigned_id != lecturer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this class")
    return lecturer

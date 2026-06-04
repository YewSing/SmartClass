from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserOut, RefreshRequest, ChangePasswordRequest
from app.core.security import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.student), selectinload(User.lecturer))
        .where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    # Generic error — never reveal whether email exists (NFR-04)
    if not user or not verify_password(body.password, user.password_hash):
        raise _INVALID_CREDS

    if user.status != "active":
        raise _INVALID_CREDS

    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not user_id or token_type != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    # Stateless JWT — client discards token. No server-side action needed.
    return


@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.student), selectinload(User.lecturer))
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    return UserOut.model_validate(user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.password_hash = hash_password(body.new_password)
    db.add(current_user)

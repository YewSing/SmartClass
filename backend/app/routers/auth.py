import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user
from app.models.user import Lecturer, Student, User
from app.schemas.auth import (
    LoginRequest, LoginResponse, MoodleLoginRequest, UserOut, RefreshRequest, ChangePasswordRequest,
)
from app.core.security import hash_password
from app.services import moodle_auth, moodle_sync
from app.services.audit_service import write_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
)
# Only sent once the password is confirmed, so it can't be used to look up who has an account
_DEACTIVATED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Your SmartClass account has been deactivated. Please contact your administrator.",
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
        raise _DEACTIVATED

    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/moodle-login", response_model=LoginResponse)
async def moodle_login(body: MoodleLoginRequest, db: AsyncSession = Depends(get_db)):
    """SPeCTRUM (Moodle) login; creates the account on first login (FR-101, FR-102)."""
    try:
        profile = await moodle_auth.authenticate(body.username, body.password)
    except moodle_auth.MoodleLoginRejected:
        raise _INVALID_CREDS from None
    except moodle_auth.MoodleUnavailable as exc:
        logger.warning("Moodle login unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPeCTRUM is not reachable right now. Please try again later.",
        ) from None

    user = await _upsert_moodle_user(db, profile)
    if user is None:
        raise _INVALID_CREDS
    await moodle_sync.sync_user(db, user, profile.courses)  # FR-104, UC step 5
    await db.commit()

    result = await db.execute(
        select(User)
        .options(selectinload(User.student), selectinload(User.lecturer))
        .where(User.id == user.id)
        .execution_options(populate_existing=True)
    )
    user = result.scalar_one()
    return LoginResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


async def _upsert_moodle_user(db: AsyncSession, profile: moodle_auth.MoodleProfile) -> User | None:
    """Find the account by Moodle id, else link one with the same email; create it if neither.
    Returns None for accounts Moodle must not sign in to (admins, or an email owned by another Moodle user)."""
    email = (profile.email or f"{profile.username}@moodle.invalid").lower()
    user = (await db.execute(
        select(User).options(selectinload(User.student), selectinload(User.lecturer))
        .where(User.moodle_user_id == profile.user_id)
    )).scalar_one_or_none()
    if user is None:
        user = (await db.execute(
            select(User).options(selectinload(User.student), selectinload(User.lecturer))
            .where(func.lower(User.email) == email)
        )).scalar_one_or_none()
        if user is not None and user.moodle_user_id is not None:
            return None
    elif user.email.lower() != email:
        taken = (await db.execute(
            select(User.id).where(func.lower(User.email) == email, User.id != user.id)
        )).first()
        if taken:
            email = user.email  # keep the old address rather than clash with another account

    if user is not None and user.role == "admin":
        return None  # administrators sign in locally only (FR-103)
    if user is not None and user.status != "active":
        raise _DEACTIVATED  # Moodle has already confirmed the password
    created = user is None
    if created:
        user = User(email=email, password_hash=None, role="student", name=profile.fullname, status="active")
        db.add(user)

    role = "lecturer" if profile.teaches else "student"
    old_role = None if created else user.role
    user.moodle_user_id = profile.user_id
    user.email = email
    user.name = profile.fullname or user.name
    user.role = role
    await db.flush()
    # The user's own login triggers these, so they are the actor (NFR-06)
    if created:
        await write_log(db, user.id, "MOODLE_ACCOUNT_CREATE", "user", user.id,
                        new_val={"email": email, "role": role, "moodle_user_id": profile.user_id})
    elif old_role != role:
        await write_log(db, user.id, "MOODLE_ROLE_CHANGE", "user", user.id,
                        old_val={"role": old_role}, new_val={"role": role})

    # Matric/staff number: Moodle's idnumber; the username only when creating a profile, so a
    # linked account's real number is never replaced by a username.
    student = None if created else user.student
    lecturer = None if created else user.lecturer
    if role == "student":
        if student is None:
            db.add(Student(user_id=user.id, matric_no=profile.idnumber or profile.username,
                           faculty=profile.department, programme=profile.fields.get("programme"),
                           year_sem=profile.fields.get("year_sem")))
        else:
            student.matric_no = profile.idnumber or student.matric_no
            student.faculty = profile.department or student.faculty
            student.programme = profile.fields.get("programme") or student.programme
            student.year_sem = profile.fields.get("year_sem") or student.year_sem
    else:
        if lecturer is None:
            db.add(Lecturer(user_id=user.id, staff_id=profile.idnumber or profile.username,
                            dept=profile.department))
        else:
            lecturer.staff_id = profile.idnumber or lecturer.staff_id
            lecturer.dept = profile.department or lecturer.dept
    await db.flush()
    return user


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
    if current_user.moodle_user_id is not None:  # Moodle owns this password (FR-101)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This account signs in through SPeCTRUM. Change its password there.")
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.password_hash = hash_password(body.new_password)
    db.add(current_user)

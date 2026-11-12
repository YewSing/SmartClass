import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

log = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"server_settings": {"timezone": "Asia/Kuala_Lumpur"}},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

_AFTER_COMMIT = "after_commit"


class Base(DeclarativeBase):
    pass


def after_commit(db: AsyncSession, callback: Callable[[], Awaitable[None]]) -> None:
    """Run `callback` once `db` has committed (websocket broadcasts, background Moodle sync).

    A client that re-reads on an event must see the change, so nothing announces a change before
    the transaction holding it commits. `get_db` runs the callbacks after its commit; code that owns
    its own session calls `run_after_commit` after committing. A rollback drops them."""
    db.info.setdefault(_AFTER_COMMIT, []).append(callback)


def discard_after_commit(db: AsyncSession) -> None:
    db.info.pop(_AFTER_COMMIT, None)


async def run_after_commit(db: AsyncSession) -> None:
    """Run (and clear) the callbacks queued on `db`. One failing never stops the others."""
    while db.info.get(_AFTER_COMMIT):
        callback = db.info[_AFTER_COMMIT].pop(0)
        try:
            await callback()
        except Exception as exc:   # an announcement must never fail the committed request
            log.warning("after-commit callback failed: %s", exc.__class__.__name__)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            discard_after_commit(session)
            await session.rollback()
            raise
        await run_after_commit(session)

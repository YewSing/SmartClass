from datetime import datetime
from zoneinfo import ZoneInfo

MYT = ZoneInfo("Asia/Kuala_Lumpur")


def now_myt() -> datetime:
    """Current Malaysia Time as a naive datetime, suitable for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(MYT).replace(tzinfo=None)

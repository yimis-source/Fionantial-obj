from datetime import datetime
from typing import Literal

TIMEZONE_OFFSETS = {
    "colombia": -5,
}


def get_current_datetime(zona: Literal["colombia"] = "colombia") -> dict:
    offset = TIMEZONE_OFFSETS.get(zona, -5)
    utc_now = datetime.utcnow()
    from datetime import timedelta
    local = utc_now + timedelta(hours=offset)
    return {
        "zona": zona,
        "fecha": local.strftime("%Y-%m-%d"),
        "hora": local.strftime("%H:%M:%S"),
        "datetime": local.strftime("%Y-%m-%d %H:%M:%S"),
        "dia_semana": local.strftime("%A"),
    }

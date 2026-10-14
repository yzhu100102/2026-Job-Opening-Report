"""Decide whether a scheduled workflow run should send the digest.

GitHub cron only speaks UTC, so the workflow fires at several UTC slots and this
script lets through only the one that lands on SEND_TIME in SEND_TZ (which also
handles daylight saving). Configure with repo variables:
  SEND_TIME  local time, "HH:MM"                    (default 09:00)
  SEND_TZ    IANA time zone, e.g. America/Chicago   (default America/Chicago)
  SEND_DAYS  "daily" or "weekdays"                  (default daily)
"""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def should_run(cron, now_utc, send_time, tz, days):
    if not cron:
        return True, "manual run"
    minute, hour = cron.split()[:2]
    # Use the slot's scheduled time, not the actual start time — GitHub often starts runs late
    slot = now_utc.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    local = slot.astimezone(ZoneInfo(tz))
    if local.strftime("%H:%M") != send_time:
        return False, f"slot is {local:%H:%M} {tz}, not {send_time}"
    if days == "weekdays" and local.weekday() >= 5:
        return False, f"{local:%A} isn't a weekday"
    return True, f"{local:%A %H:%M} {tz}"


if __name__ == "__main__":
    run, reason = should_run(
        os.environ.get("CRON", ""),
        datetime.now(timezone.utc),
        os.environ.get("SEND_TIME") or "09:00",
        os.environ.get("SEND_TZ") or "America/Chicago",
        os.environ.get("SEND_DAYS") or "daily",
    )
    print(("Sending: " if run else "Skipping: ") + reason)
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"run={'true' if run else 'false'}\n")

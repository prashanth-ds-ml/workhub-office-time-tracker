from __future__ import annotations

import argparse

import app
from storage import clear_rows, reset_first_admin_claim, storage_backend


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove WorkHub users and operational data.")
    parser.add_argument("--confirm", action="store_true", help="Required confirmation flag")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("Refusing to reset data without --confirm")

    for path in [
        app.USERS_FILE,
        app.SESSIONS_FILE,
        app.BREAKS_FILE,
        app.CALENDAR_EVENTS_FILE,
        app.HOLIDAY_MASTER_FILE,
        app.ANNOUNCEMENTS_FILE,
        app.COMPANY_EVENTS_FILE,
        app.ANNOUNCEMENT_READS_FILE,
        app.ALERT_ACK_FILE,
    ]:
        clear_rows(path)
    reset_first_admin_claim()
    app._refresh_cache()
    print(f"WorkHub operational data cleared from {storage_backend()} storage.")


if __name__ == "__main__":
    main()

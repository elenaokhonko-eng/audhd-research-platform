from datetime import UTC, datetime

EMAIL: dict[str, str] = {
    name: f"{name}@example.org" for name in ("ana", "bo", "cy", "di", "ed", "fay", "gus", "hal")
}

T0 = datetime(2026, 11, 20, tzinfo=UTC)

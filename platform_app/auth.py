from dataclasses import dataclass

from platform_app.settings import Settings


@dataclass(frozen=True, slots=True)
class Principal:
    email: str
    roles: frozenset[str]

    def require(self, *roles: str) -> None:
        if not self.roles.intersection(roles):
            raise PermissionError(f"Requires one of roles: {', '.join(roles)}")


def local_principal(settings: Settings) -> Principal:
    if settings.environment not in {"development", "test"}:
        raise PermissionError("Local authentication is disabled outside development/test")
    return Principal(settings.local_auth_email, frozenset({"admin", "researcher", "reviewer", "publisher"}))


def roles_for_email(email: str, settings: Settings) -> frozenset[str]:
    admins = {item.strip().lower() for item in settings.admin_emails.split(",") if item.strip()}
    base = {"researcher", "reviewer"}
    if email.lower() in admins:
        base.update({"admin", "publisher"})
    return frozenset(base)

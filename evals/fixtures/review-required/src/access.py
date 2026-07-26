from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    is_authenticated: bool
    is_admin: bool


def can_delete_account(actor: Actor) -> bool:
    return actor.is_authenticated and actor.is_admin

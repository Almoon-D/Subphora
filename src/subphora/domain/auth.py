# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The login's models and failures (MASTER_PLAN §4.9): a few named users, no sign-up."""

from enum import StrEnum

from pydantic import Field

from subphora.domain import DomainModel

# A user's name: lower case letters, digits, dot, dash and underscore. It is a login, not
# a person's full name, and never appears in a log.
USER_NAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,31}$"


class AuthFailure(StrEnum):
    UNAUTHENTICATED = "unauthenticated"
    WRONG_CREDENTIALS = "wrong_credentials"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    INVALID_NAME = "invalid_name"
    WEAK_PASSWORD = "weak_password"
    USER_EXISTS = "user_exists"
    UNKNOWN_USER = "unknown_user"
    STORE_UNAVAILABLE = "store_unavailable"


class AuthError(Exception):
    """A refusal of the login or of a user command; ``retry_after_s`` for a lockout."""

    def __init__(self, failure: AuthFailure, detail: str, retry_after_s: int = 0) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = detail
        self.retry_after_s = retry_after_s


class Credentials(DomainModel):
    """The body of ``POST /api/auth/login``. The lengths are checked by the service, so a
    long password is refused with the same answer as a wrong one."""

    name: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=4096)


class SignedIn(DomainModel):
    """Who the session belongs to."""

    name: str

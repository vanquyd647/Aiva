"""Auth schema models."""

from pydantic import BaseModel

from app.schemas.user import UserOut


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    session_id: str | None = None

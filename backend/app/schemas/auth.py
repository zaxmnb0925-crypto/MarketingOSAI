from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    full_name: str = Field(
        min_length=1,
        max_length=120,
    )

    workspace_name: str = Field(
        min_length=1,
        max_length=150,
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None
    is_active: bool


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str


class MeResponse(BaseModel):
    user: UserResponse
    workspaces: list[WorkspaceResponse]

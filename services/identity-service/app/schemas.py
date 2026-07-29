from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MembershipOut(BaseModel):
    code: str
    role: str
    permissions: list[str]


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    system_role: str | None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    modules: list[MembershipOut]


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class AssignMembershipRequest(BaseModel):
    module_code: str = Field(pattern="^(HQA|HQS)$")
    role: str = Field(pattern="^(admin|user)$")


class UserStatusRequest(BaseModel):
    is_active: bool

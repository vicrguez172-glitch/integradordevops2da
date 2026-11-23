from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class AdminUserCreate(UserCreate):
    role: str = "customer"

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"customer", "admin"}:
            raise ValueError("El rol debe ser customer o admin")
        return value


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str | None) -> str | None:
        if value is not None and value not in {"customer", "admin"}:
            raise ValueError("El rol debe ser customer o admin")
        return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class GameCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    platform: str = Field(min_length=2, max_length=40)
    category: str = Field(min_length=2, max_length=40)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    image_url: str = Field(min_length=1, max_length=500)
    stock: int = Field(ge=0, le=10000)


class GameUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    platform: str | None = Field(default=None, min_length=2, max_length=40)
    category: str | None = Field(default=None, min_length=2, max_length=40)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    image_url: str | None = Field(default=None, min_length=1, max_length=500)
    stock: int | None = Field(default=None, ge=0, le=10000)


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    platform: str
    category: str
    price: Decimal
    image_url: str
    stock: int


class PurchaseLine(BaseModel):
    game_id: int
    quantity: int = Field(ge=1, le=10)


class PurchaseCreate(BaseModel):
    items: list[PurchaseLine] = Field(min_length=1, max_length=20)


class PurchaseItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game_id: int
    game_title: str
    quantity: int
    unit_price: Decimal


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total: Decimal
    status: str
    created_at: datetime
    items: list[PurchaseItemOut]


class HealthOut(BaseModel):
    status: str

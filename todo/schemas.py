from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# from pydantic.networks import EmailStr

# Pydantic models for request/response validation

# ====================== Task Schemas ======================
class TaskBase(BaseModel):
    """Base schema for common fields"""
    title: str = Field(
        ...,  # this field must not be null or empty
        min_length=1,
        max_length=200,
        description="Task title",
        #  strip_whitespace=True, # deprecated
        json_schema_extra={"strip_whitespace": True}  # New way
    )


class TaskCreate(TaskBase):
    """Schema for creating a new task """
    model_config = {"from_attributes": True}


class Task(TaskBase):
    """Full task response (includes id, done, created_at)"""
    id: int
    done: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}  # New way

    # Allows SQLAlchemy models to be converted to this
    # from_attributes = True allows Pydantic to read data from object attributes (instead of only from dictionaries).
    # This is crucial when you want to convert SQLAlchemy ORM objects into Pydantic models.


# ====================== User Schemas ======================
class UserBase(BaseModel):
    """Base user fields"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username"
    )
    email: Optional[EmailStr] = Field(None, description="User email address")
    # role: str = "user"  # No role field here, we will manage in database layer for security reasons


# while creating User
class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(
        ...,
        min_length=8,
        description="User password"
    )


# for Response object
class User(UserBase):
    """User response model"""
    id: int
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


# ====================== Task Schemas ======================

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class TokenRefresh(BaseModel):
    refresh_token: str

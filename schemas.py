from typing import Annotated

from fastapi import Path, HTTPException
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Модель создания пользователя."""
    username: str


class UserResponse(BaseModel):
    """Модель ответа с данными пользователя."""
    id: int
    username: str


class CityCreate(BaseModel):
    """Модель создания города."""
    name: str
    latitude: float = Field(ge=-90, le=90, description="Широта должна быть в диапазоне от -90 до 90")
    longitude: float = Field(ge=-180, le=180, description="Долгота должна быть в диапазоне от -180 до 180")


class CityResponse(BaseModel):
    """Модель ответа с данными города."""
    id: int
    name: str


class WeatherResponse(BaseModel):
    """Модель ответа с данными о погоде."""
    temperature: float
    wind_speed: float
    pressure: float

async def validate_user_id(
    user_id: Annotated[int, Path(ge=1, description="ID пользователя должен быть положительным числом")]
) -> int:
    if user_id < 1:
        raise HTTPException(status_code=400, detail="ID пользователя должен быть положительным числом")
    return user_id

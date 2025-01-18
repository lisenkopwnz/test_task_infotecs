from typing import Annotated

from fastapi import Path, HTTPException
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Модель создания пользователя."""
    username: str = Field(..., description="Имя пользователя", min_length=1, max_length=50)


class UserResponse(BaseModel):
    """Модель ответа с данными пользователя."""
    id: int = Field(..., description="Уникальный идентификатор пользователя")
    username: str = Field(..., description="Имя пользователя")


class CityCreate(BaseModel):
    """Модель создания города."""
    name: str = Field(..., description="Название города", min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90, le=90, description="Широта должна быть в диапазоне от -90 до 90")
    longitude: float = Field(..., ge=-180, le=180, description="Долгота должна быть в диапазоне от -180 до 180")


class CityResponse(BaseModel):
    """Модель ответа с данными города."""
    name: str = Field(..., description="Название города")


class WeatherResponse(BaseModel):
    """Модель ответа с данными о погоде."""
    temperature: float = Field(..., description="Температура в градусах Цельсия")
    wind_speed: float = Field(..., description="Скорость ветра в км/ч")
    pressure: float = Field(..., description="Атмосферное давление в гектопаскалях (hPa)")


async def validate_user_id(
    user_id: Annotated[int, Path(ge=1, description="ID пользователя должен быть положительным числом")]
) -> int:
    """
    Валидирует ID пользователя.
    """
    if user_id < 1:
        raise HTTPException(
            status_code=400,
            detail="ID пользователя должен быть положительным числом"
        )
    return user_id

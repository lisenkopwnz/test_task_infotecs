from contextlib import asynccontextmanager
from shutil import which
from typing import Annotated, Dict, Any
import httpx
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = "sqlite+aiosqlite:///./weather.db"
engine = create_async_engine(DATABASE_URL, echo = True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit =False,
)

Base = declarative_base()

class City(Base):
    __tablename__ = "cities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, prymary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)

class UserCity(Base):
    __tablename__ = "user_cities"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    city_id = Column(Integer, ForeignKey("cities.id"), primary_key=True)

class Weather(Base):
    __tablename__ = "weather"
    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"))
    temperature = Column(Float)
    wind_speed = Column(Float)
    pressure = Column(Float)
    timestamp = Column(Float)

@asynccontextmanager
async def lifespan():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
        
app = FastAPI()

class WeatherResponse(BaseModel):
    latitude: float
    longitude: float
    temperature: float
    wind_speed: float
    pressure: float



async def get_current_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Получает текущие погодные данные для указанных координат.

    Args:
        latitude (float): Широта места.
        longitude (float): Долгота места.

    Returns:
        Dict[str, Any]: JSON-ответ с данными о погоде.

    Raises:
        HTTPException: Если произошла ошибка при запросе к API.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,  # Параметр для получения текущей погоды
        "hourly": "pressure_msl",  # Добавляем параметр для получения атмосферного давления
        "timezone": "auto",
    }

    # Настройка тайм-аутов
    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

    # Настройка транспорта с повторными попытками
    transport = httpx.AsyncHTTPTransport(retries=3)

    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()  # Проверка на ошибки HTTP
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = {
                "status_code": e.response.status_code,
                "message": str(e),
                "response_text": e.response.text,
            }
            raise HTTPException(status_code=500, detail=error_detail)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Произошла ошибка: {str(e)}"
            )


# Эндпоинт для получения текущей погоды
@app.get("/weather/current-conditions", response_model=WeatherResponse)
async def current_weather(
    latitude: Annotated[float, Query(ge=-90, le=90, description="Широта должна быть между -90 и 90")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Долгота должна быть между -180 и 180")]
):
    # Получаем данные о погоде
    response_data = await get_current_weather(latitude, longitude)

    # Проверяем, что поле "current_weather" есть в ответе
    if "current_weather" not in response_data:
        raise HTTPException(
            status_code=500,
            detail="Данные о текущей погоде недоступны"
        )

    # Извлекаем данные о текущей погоде
    current = response_data["current_weather"]

    # Пытаемся извлечь данные о давлении (если они есть)
    pressure = None
    if "hourly" in response_data and "pressure_msl" in response_data["hourly"]:
        pressure = response_data["hourly"]["pressure_msl"][0]  # Берем первое значение из массива

    # Возвращаем данные в формате WeatherResponse
    return WeatherResponse(
        latitude=latitude,
        longitude=longitude,
        temperature=current["temperature"],
        wind_speed=current["windspeed"],
        pressure=pressure if pressure is not None else 0  # Если давление недоступно, возвращаем 0 или None
    )

@app.get("/")
def main():
    return {"d":
            "d"}
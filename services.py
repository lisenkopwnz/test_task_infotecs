import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import httpx
from fastapi import HTTPException, Depends
from typing import Dict, Any
import httpx
from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from starlette import status

from database import AsyncSessionLocal
from dependencies import get_db
from models import Weather, City, User


async def get_user_or_404(db: AsyncSession, user_id: int) :
    """
    Получает пользователя по его ID из базы данных.
    Если пользователь с данным ID не существует, вызывает исключение 404.
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Такого пользователя нет")

async def save_weather_forecast(db: AsyncSession, city_id: int, weather_data: Dict[str, Any]):
    """
    Сохраняет прогноз погоды в таблицу Weather.
    """
    hourly_data = weather_data.get("hourly", {})
    times = hourly_data.get("time", [])
    temperatures = hourly_data.get("temperature_2m", [])
    humidities = hourly_data.get("relativehumidity_2m", [])
    wind_speeds = hourly_data.get("windspeed_10m", [])
    precipitations = hourly_data.get("precipitation", [])

    # Создаём список записей для сохранения
    weather_records = []
    for i in range(len(times)):
        forecast_time = datetime.fromisoformat(times[i])
        weather_record = Weather(
            city_id=city_id,
            forecast_time=forecast_time,
            temperature=temperatures[i],
            humidity=humidities[i],
            wind_speed=wind_speeds[i],
            precipitation=precipitations[i],
        )
        weather_records.append(weather_record)

    # Сохраняем все записи за один раз
    db.add_all(weather_records)
    await db.commit()

















async def delete_old_weather_data(db: AsyncSession):
    try:
        current_time = datetime.now(timezone.utc)
        stmt = delete(Weather).where(Weather.forecast_time < current_time)
        await db.execute(stmt)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise
    except Exception as e:
        raise

async def update_weather_data(db: AsyncSession = Depends(get_db)):
    cities = await db.execute(select(City))
    cities = cities.scalars().all()
    for city in cities:
        weather_data = await get_current_weather(city.latitude, city.longitude)

        hourly_data = weather_data["hourly"]
        for i in range(len(hourly_data["time"])):
            forecast_time = datetime.fromisoformat(hourly_data["time"][i])
            weather = Weather(
                city_id=city.id,
                forecast_time=forecast_time,
                temperature=hourly_data["temperature_2m"][i],
                humidity=hourly_data["relativehumidity_2m"][i],
                wind_speed=hourly_data["windspeed_10m"][i],
                precipitation=hourly_data["precipitation"][i],
                timestamp=datetime.now(timezone.utc)
            )
            db.add(weather)
        await db.commit()

    await asyncio.sleep(900)



async def get_current_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Получает данные о погоде для указанных координат.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "hourly": "temperature_2m,relativehumidity_2m,pressure_msl,windspeed_10m,precipitation",   # Добавлен relativehumidity_2m
        "forecast_days": 1,
        "timezone": "auto",
    }

    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
    transport = httpx.AsyncHTTPTransport(retries=3)

    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "status_code": e.response.status_code,
                    "message": str(e),
                    "response_text": e.response.text,
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Произошла ошибка: {str(e)}"
            )

#def round_to_nearest_hour(target_time: time) -> time:
    """
    Округляет время до ближайшего часа.
    Например:
    - 10:07 -> 10:00
    - 10:37 -> 11:00
    - 23:45 -> 00:00
    """
    # Преобразуем time в datetime для удобства вычислений
    #dummy_date = datetime(1, 1, 1)  # Фиктивная дата
    #full_datetime = datetime.combine(dummy_date, target_time)

    # Округляем
    #if full_datetime.minute >= 30:
        #rounded_datetime = full_datetime.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    #else:
        #rounded_datetime = full_datetime.replace(minute=0, second=0, microsecond=0)

    # Возвращаем только время
    #return rounded_datetime.time()
import asyncio
import logging
from datetime import datetime, timezone, timedelta, time
from typing import Dict, Any

import httpx
from fastapi import HTTPException
from starlette import status
from zoneinfo import ZoneInfo

from file_handlers import save_data, load_data, WEATHER_FILE, CITIES_FILE

logger = logging.getLogger(__name__)

async def get_or_404(user_id: int, users_data: Dict[str, Any]):
    """
    Проверяем существует ли польователь в базе данных
    """
    if str(user_id) not in users_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

async def save_weather_forecast(city_id: str, weather_data: Dict[str, Any]):
    """
    Сохраняет прогноз погоды в файл weather.json.
    """
    hourly_data = weather_data.get("hourly", {})
    times = hourly_data.get("time", [])
    temperatures = hourly_data.get("temperature_2m", [])
    humidities = hourly_data.get("relativehumidity_2m", [])
    wind_speeds = hourly_data.get("windspeed_10m", [])
    precipitations = hourly_data.get("precipitation", [])

    # Загружаем текущие данные о погоде
    weather = await load_data(WEATHER_FILE)

    # Создаем записи о погоде для города
    weather[city_id] = {}
    for i in range(len(times)):
        forecast_time = times[i]  # Время прогноза (строка в формате ISO)
        weather[city_id][forecast_time] = {
            "temperature": temperatures[i],
            "humidity": humidities[i],
            "wind_speed": wind_speeds[i],
            "precipitation": precipitations[i],
        }
    # Сохраняем обновленные данные
    await save_data(WEATHER_FILE, weather)

async def get_current_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Получает данные о погоде для указанных координат.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "hourly": "temperature_2m,relativehumidity_2m,pressure_msl,windspeed_10m,precipitation",
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

async def update_weather_data():
    """
    Обновляет данные о погоде для всех городов каждые 15 минут.
    """
    while True:
        # Загружаем данные о городах
        cities = await load_data(CITIES_FILE)

        # Загружаем данные о погоде
        weather_data = await load_data(WEATHER_FILE)

        # Удаляем старые записи (старше 24 часов)
        await delete_old_weather_data(weather_data, cities)

        # Обновляем данные для каждого города
        for city_id, city_info in cities.items():
            latitude = city_info["latitude"]
            longitude = city_info["longitude"]

            try:
                # Получаем данные о погоде
                current_weather = await get_current_weather(latitude, longitude)

                # Обновляем данные в json
                if city_id not in weather_data:
                    weather_data[city_id] = {}

                hourly_data = current_weather["hourly"]
                for i in range(len(hourly_data["time"])):
                    timestamp = hourly_data["time"][i]
                    weather_data[city_id][timestamp] = {
                        "temperature": hourly_data["temperature_2m"][i],
                        "humidity": hourly_data["relativehumidity_2m"][i],
                        "wind_speed": hourly_data["windspeed_10m"][i],
                        "precipitation": hourly_data["precipitation"][i]
                    }

            except Exception as e:
                logger.info(f"Ошибка при обновлении данных для города {city_id}: {e}")

        # Сохраняем данные
        await save_data(WEATHER_FILE, weather_data)

        # Ждем 15 минут перед следующим обновлением
        await asyncio.sleep(900)

async def delete_old_weather_data(weather_data: Dict[str, Any], cities: Dict[str, Any]):
    """
    Удаляет записи о погоде, которые старше 24 часов.
    """
    now_utc = datetime.now(timezone.utc)  # Текущее время в UTC

    for city_id, city_weather in weather_data.items():
        # Получаем временную метку города
        city_timezone = ZoneInfo(cities[city_id]["timezone"])

        # Создаем копию словаря
        for timestamp in list(city_weather.keys()):
            # Преобразуем локальное время в объект datetime с временной меткой
            local_time = datetime.fromisoformat(timestamp).replace(tzinfo=city_timezone)

            # Преобразуем локальное время в UTC
            utc_time = local_time.astimezone(timezone.utc)

            # Удаляем записи, старше 24 часов
            if (now_utc - utc_time) > timedelta(hours=24):
                del city_weather[timestamp]

def round_to_nearest_hour(target_time: time) -> time:
    """
    Округляет время до ближайшего часа.
    Например:
    - 10:07 -> 10:00
    - 10:37 -> 11:00
    - 23:45 -> 00:00
    """
    # Преобразуем time в datetime для удобства вычислений
    dummy_date = datetime(1, 1, 1)  # Фиктивная дата
    full_datetime = datetime.combine(dummy_date, target_time)

    # Округляем
    if full_datetime.minute >= 30:
        rounded_datetime = full_datetime.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        rounded_datetime = full_datetime.replace(minute=0, second=0, microsecond=0)

    # Возвращаем только время
    return rounded_datetime.time()

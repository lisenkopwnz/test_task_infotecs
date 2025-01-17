from typing import List, Annotated
from datetime import datetime, UTC
from fastapi import Query, APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import extract
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from sqlalchemy.future import select
from dependencies import get_db
from models import UserCity, User, City, Weather
from schemas import UserResponse, UserCreate, CityCreate, validate_user_id, CityResponse, WeatherResponse
from services import get_current_weather, get_user_or_404, save_weather_forecast

router = APIRouter()

@router.post(
    "/users",
    response_model=UserResponse,
    summary="Создание нового пользователя"
)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(**user.model_dump())
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует",
        )

@router.post(
    "/users/{user_id}/cities/add",
    summary="Добавить город для пользователя",
    response_description="Сообщение о результате операции",
    responses={
        200: {"description": "Город добавлен или уже связан с пользователем"},
        404: {"description": "Пользователь не найден"},
    },
)
async def add_city_for_user(
    city: CityCreate,
    user_id: int = Depends(validate_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Проверка наличия пользователя
    await get_user_or_404(db, user_id)

    # Поиск города, если нет — создаём
    db_city = await db.execute(select(City).where(City.name == city.name))
    db_city = db_city.scalar_one_or_none()

    # Если город новый, добавляем в базу
    if not db_city:
        db_city = City(**city.model_dump())
        db.add(db_city)
        await db.commit()
        await db.refresh(db_city)

    # Проверка существования связи с городом
    existing_link = await db.execute(select(UserCity)
                                     .where(UserCity.user_id == user_id, UserCity.city_id == db_city.id))
    if existing_link.scalar_one_or_none():
        return {"message": "Пользователь уже добавил этот город"}

    # Создаём связь
    db.add(UserCity(user_id=user_id, city_id=db_city.id))
    await db.commit()

    # Получаем прогноз погоды для города
    try:
        weather_data = await get_current_weather(db_city.latitude, db_city.longitude)
        await save_weather_forecast(db, db_city.id, weather_data)
    except Exception as e:
        return f"Ошибка при получении или сохранении прогноза погоды: {str(e)}"

    return {"message": "Город успешно добавлен"}










@router.get(
    "/users/{user_id}/cities/",
    response_model=List[CityResponse],
    summary="Получить список городов пользователя",
    description="Возвращает список всех городов, связанных с указанным пользователем.",
    response_description="Список городов пользователя",
)
async def get_user_cities(
    user_id: int = Depends(validate_user_id),
    db: AsyncSession = Depends(get_db)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(City)
        .join(UserCity, City.id == UserCity.city_id)
        .where(UserCity.user_id == user_id)
    )
    cities = result.scalars().all()

    if not cities:
        raise HTTPException(status_code=404, detail="No cities found for this user")

    return cities

@router.get(
    "/weather/current-conditions",
    response_model=WeatherResponse,
    summary="Получить текущие погодные условия",
    description="""
    Этот эндпоинт возвращает текущие погодные условия для указанных координат (широта и долгота).

    ### Параметры:
    - **latitude**: Широта (от -90 до 90).
    - **longitude**: Долгота (от -180 до 180).

    ### Возвращает:
    - **temperature**: Текущая температура в градусах Цельсия.
    - **wind_speed**: Скорость ветра в км/ч.
    - **pressure**: Атмосферное давление в гектопаскалях (hPa).
    """,
    response_description="Данные о текущей погоде",
)
async def current_weather(
    latitude: Annotated[float, Query(ge=-90, le=90, description="Широта должна быть между -90 и 90")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Долгота должна быть между -180 и 180")]
):
    # Получаем данные от API
    response_data = await get_current_weather(latitude, longitude)

    # Проверяем наличие данных о текущей погоде
    if "current_weather" not in response_data:
        raise HTTPException(
            status_code=500,
            detail="Данные о текущей погоде недоступны"
        )

    # Извлекаем текущие данные погоды
    current_weather_data = response_data["current_weather"]

    # Берём первое значение давления
    pressure_msl = response_data["hourly"]["pressure_msl"][0] if "hourly" in response_data else 0

    return WeatherResponse(
        temperature=current_weather_data["temperature"],
        wind_speed=current_weather_data["windspeed"],
        pressure=pressure_msl,
    )

@router.get(
    "/users/{user_id}/weather",
    summary="Получить данные о погоде для города пользователя",
    description="Возвращает данные о погоде для указанного города и времени. Время должно быть в формате 'HH:MM'.",
    response_description="Данные о погоде в формате JSON."
)
async def get_weather_at_time(
    city_name: str,
    time: str,
    user_id: int = Depends(validate_user_id),
    parameters: str = Query(default="temperature,humidity,wind_speed,precipitation"),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Преобразуем время пользователя в формат datetime.time
        target_time = datetime.strptime(time, "%H:%M").time()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Некорректный формат времени. Используйте формат 'HH:MM'."
        )

    # Проверяем, что город есть в списке пользователя
    city_result = await db.execute(
        select(City)
        .join(UserCity, UserCity.city_id == City.id)
        .where(City.name == city_name)
        .where(UserCity.user_id == user_id)
    )
    city = city_result.scalar_one_or_none()

    if not city:
        raise HTTPException(
            status_code=404,
            detail=f"Город '{city_name}' не найден в списке пользователя."
        )

    # Получаем данные о погоде, фильтруя только по времени (час:минуты)
    weather_result = await db.execute(
        select(Weather)
        .where(Weather.city_id == city.id)
        .where(extract('hour', Weather.forecast_time) == target_time.hour)
        .where(extract('minute', Weather.forecast_time) == target_time.minute)
    )
    weather = weather_result.scalar_one_or_none()

    if not weather:
        raise HTTPException(
            status_code=404,
            detail=f"Данные о погоде для города '{city_name}' на время '{target_time.strftime('%H:%M')}' не найдены."
        )

    # Фильтруем параметры погоды
    selected_parameters = parameters.split(",")
    response = {}
    for param in selected_parameters:
        if param == "temperature":
            response["temperature"] = weather.temperature
        elif param == "humidity":
            response["humidity"] = weather.humidity
        elif param == "wind_speed":
            response["wind_speed"] = weather.wind_speed
        elif param == "precipitation":
            response["precipitation"] = weather.precipitation

    if not response:
        raise HTTPException(
            status_code=400,
            detail="Указаны недопустимые параметры. Доступные параметры: temperature, humidity, wind_speed, precipitation."
        )

    return response


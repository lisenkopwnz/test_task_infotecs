import logging
from datetime import datetime
from typing import Annotated, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status

from file_handlers import CITIES_FILE, USERS_FILE, WEATHER_FILE, load_data, save_data
from schemas import (
    CityCreate,
    CityResponse,
    UserCreate,
    UserResponse,
    WeatherResponse,
    validate_user_id,
)
from services import (
    get_current_weather,
    get_or_404,
    round_to_nearest_hour,
    save_weather_forecast,
)
router = APIRouter()

logger = logging.getLogger(__name__)

@router.post(
    "/users",
    response_model=UserResponse,
    summary="Создание нового пользователя",
    description="Создает нового пользователя с уникальным именем. Если пользователь с таким именем уже существует, возвращает ошибку 400.",
    responses={
        200: {"description": "Пользователь успешно создан"},
        400: {"description": "Пользователь с таким именем уже существует"},
    },
)
async def create_user(user: UserCreate):
    """
    Создает нового пользователя.

    Args:
        user (UserCreate): Данные для создания пользователя, включая имя пользователя.

    Returns:
        UserResponse: Ответ с ID и именем созданного пользователя.

    Raises:
        HTTPException: Если пользователь с таким именем уже существует.
    """
    # Загружаем данные о пользователях
    users = await load_data(USERS_FILE)

    # Проверяем, существует ли пользователь с таким именем
    for user_id, user_data in users.items():
        if user_data["username"] == user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким именем уже существует",
            )

    # Генерируем новый user_id
    if users:  # Если файл не пустой
        user_id = str(max(int(user_id) for user_id in users.keys()) + 1)
    else:  # Если файл пустой
        user_id = "1"

    # Создаем нового пользователя
    users[user_id] = {"username": user.username, "cities": []}
    await save_data(USERS_FILE, users)

    return {"id": user_id, "username": user.username}

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
):
    """
    Добавляет город для указанного пользователя.

    Если город не существует в базе данных, он создается, и для него запрашивается прогноз погоды.
    Если город уже связан с пользователем, возвращается соответствующее сообщение.

    Args:
        city (CityCreate): Данные о городе (название, широта, долгота).
        user_id (int): ID пользователя, для которого добавляется город.

    Returns:
        dict: Сообщение о результате операции.

    Raises:
        HTTPException: Если пользователь не найден или произошла ошибка при запросе погоды.
    """
    # Загружаем данные
    users = await load_data(USERS_FILE)
    cities = await load_data(CITIES_FILE)

    # Проверяем, существует ли пользователь
    await get_or_404(user_id, users)

    # Ищем город по имени
    city_id = None
    for c_id, c_data in cities.items():
        if c_data["name"] == city.name:
            city_id = c_id
            break

    # Если город не найден, добавляем его
    if not city_id:
        city_id = str(len(cities) + 1)

        # Получаем прогноз погоды для нового города
        try:
            weather_data = await get_current_weather(city.latitude, city.longitude)
            timezone = weather_data.get("timezone")  # Извлекаем временную зону

            # Сохраняем данные о городе
            cities[city_id] = {
                "name": city.name,
                "latitude": city.latitude,
                "longitude": city.longitude,
                "timezone": timezone,  # Добавляем временную зону
            }
            await save_data(CITIES_FILE, cities)

            # Сохраняем прогноз погоды
            await save_weather_forecast(city_id, weather_data)
        except HTTPException as e:
            return {"message": f"Ошибка при получении прогноза погоды: {e.detail}"}
        except Exception as e:
            return {"message": f"Произошла ошибка: {str(e)}"}

    # Проверяем, есть ли связь между пользователем и городом
    user_cities = users[str(user_id)].get("cities", [])
    if city_id in user_cities:
        return {"message": "Пользователь уже добавил этот город"}

    # Добавляем город в список городов пользователя
    user_cities.append(city_id)
    users[str(user_id)]["cities"] = user_cities
    await save_data(USERS_FILE, users)

    return {"message": "Город успешно добавлен"}

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
    responses={
        200: {"description": "Данные о текущей погоде успешно получены"},
        500: {"description": "Ошибка при получении данных о погоде"},
    },
)
async def current_weather(
    latitude: Annotated[float, Query(ge=-90, le=90, description="Широта должна быть между -90 и 90")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Долгота должна быть между -180 и 180")]
) -> WeatherResponse:
    """
    Получает текущие погодные условия для указанных координат.

    Args:
        latitude (float): Широта (от -90 до 90).
        longitude (float): Долгота (от -180 до 180).

    Returns:
        WeatherResponse: Данные о текущей погоде, включая температуру, скорость ветра и давление.

    Raises:
        HTTPException: Если данные о погоде недоступны или произошла ошибка при запросе.
    """
    # Получаем данные от API
    response_data = await get_current_weather(latitude, longitude)

    # Проверяем наличие данных о текущей погоде
    if "current_weather" not in response_data:
        raise HTTPException(
            status_code=500,
            detail="Данные о текущей погоде недоступны"
        )

    # Извлекаем текущие данные прогноза погоды
    current_weather_data = response_data["current_weather"]

    # Берём первое  давление
    pressure_msl = response_data["hourly"]["pressure_msl"][0] if "hourly" in response_data else 0

    return WeatherResponse(
        temperature=current_weather_data["temperature"],
        wind_speed=current_weather_data["windspeed"],
        pressure=pressure_msl,
    )

@router.get(
    "/users/{user_id}/cities/",
    response_model=List[CityResponse],
    summary="Получить список городов пользователя",
    description="Возвращает список всех городов, связанных с указанным пользователем.",
    response_description="Список городов пользователя",
    responses={
        200: {"description": "Список городов успешно получен"},
        404: {"description": "Пользователь не найден или города отсутствуют"},
    },
)
async def get_user_cities(
    user_id: int = Depends(validate_user_id),
) -> List[CityResponse]:
    """
    Получает список городов, связанных с указанным пользователем.

    Args:
        user_id (int): ID пользователя.

    Returns:
        List[CityResponse]: Список городов пользователя.

    Raises:
        HTTPException: Если пользователь не найден или у пользователя нет городов.
    """
    # Загружаем данные о клиентах и городах
    users = await load_data(USERS_FILE)
    cities = await load_data(CITIES_FILE)

    # Проверяем, существует ли пользователь
    await get_or_404(user_id, users)

    # Получаем список id городов
    user_city_ids = users[str(user_id)].get("cities", [])

    # Получаем данные о городах
    user_cities = []
    for city_id in user_city_ids:
        if str(city_id) in cities:
            city_name = cities[str(city_id)].get("name")
            if city_name:
                user_cities.append(CityResponse(name=city_name))

    if not user_cities:
        raise HTTPException(status_code=404, detail="У пользователя нет городов")

    return user_cities

@router.get(
    "/users/{user_id}/weather",
    summary="Получить данные о погоде для города пользователя",
    description="Возвращает данные о погоде для указанного города и времени. Время должно быть в формате 'HH:MM'.",
    response_description="Данные о погоде в формате JSON."
)
async def get_weather_at_time(
    city_name: str,
    time_str: str,
    user_id: int = Depends(validate_user_id),
    parameters: str = Query(default="temperature,humidity,wind_speed,precipitation"),
) -> Dict[str, Any]:
    try:
        # Преобразуем время пользователя в формат datetime.time
        target_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Некорректный формат времени. Используйте формат 'HH:MM'."
        )

    # Округляем время до ближайшего часа
    rounded_time = round_to_nearest_hour(target_time)

    # Загружаем данные о пользователях и городах
    users = await load_data(USERS_FILE)
    cities = await load_data(CITIES_FILE)
    weather_data = await load_data(WEATHER_FILE)

    # Проверяем, что пользователь существует
    if str(user_id) not in users:
        raise HTTPException(
            status_code=404,
            detail=f"Пользователь с ID {user_id} не найден."
        )

    # Проверяем, что город есть в списке пользователя
    user_cities = users[str(user_id)].get("cities", [])
    city_id = None
    for city in user_cities:
        if cities.get(str(city), {}).get("name") == city_name:
            city_id = str(city)
            break

    if not city_id:
        raise HTTPException(
            status_code=404,
            detail=f"Город '{city_name}' не найден в списке пользователя."
        )

    # Получаем данные о погоде для города
    city_weather = weather_data.get(city_id, {})
    if not city_weather:
        raise HTTPException(
            status_code=404,
            detail=f"Данные о погоде для города '{city_name}' не найдены."
        )

    # Ищем данные для округленного времени
    rounded_time_str = rounded_time.strftime("%H:%M")
    weather_at_time = None
    for timestamp, weather in city_weather.items():
        if timestamp.endswith(rounded_time_str):
            weather_at_time = weather
            break

    if not weather_at_time:
        raise HTTPException(
            status_code=404,
            detail=f"Данные о погоде для города '{city_name}' на время '{rounded_time_str}' не найдены."
        )

    # Фильтруем параметры погоды с использованием match-case
    selected_parameters = parameters.split(",")
    response = {}
    for param in selected_parameters:
        match param:
            case "temperature":
                response["temperature"] = weather_at_time.get("temperature")
            case "humidity":
                response["humidity"] = weather_at_time.get("humidity")
            case "wind_speed":
                response["wind_speed"] = weather_at_time.get("wind_speed")
            case "precipitation":
                response["precipitation"] = weather_at_time.get("precipitation")
            case _:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недопустимый параметр: {param}. Доступные параметры: temperature, humidity, wind_speed, precipitation."
                )

    if not response:
        raise HTTPException(
            status_code=400,
            detail="Указаны недопустимые параметры. Доступные параметры: temperature, humidity, wind_speed, precipitation."
        )

    return response

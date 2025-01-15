from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import Annotated, Dict, Any, List
import httpx
from fastapi import FastAPI, Path, HTTPException, Depends, Query
from fastapi.params import Depends
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from starlette import status

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
    id = Column(Integer, primary_key=True, index=True)
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
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

app = FastAPI(lifespan=lifespan)

async def validate_user_id(
    user_id: Annotated[int, Path(ge=1, description="ID пользователя должен быть положительным числом")]
) -> int:

    if user_id < 1:
        raise HTTPException(status_code=400, detail="ID пользователя должен быть положительным числом")
    return user_id

class UserCreate(BaseModel):
    username: str

class UserResponse(BaseModel):
    id: int
    username: str

class CityCreate(BaseModel):
    name: str
    latitude: float = Field(ge=-90, le=90, description="Широта должна быть в диапазоне от -90 до 90")
    longitude: float = Field(ge=-180, le=180, description="Долгота должна быть в диапазоне от -180 до 180")

class CityResponse(BaseModel):
    id: int
    name: str

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

@app.post(
    "/users",
    response_model=UserResponse,
    summary="Создание нового пользователя",
    description="""
    Этот эндпоинт позволяет создать нового пользователя в системе.

    - **username**: Уникальное имя пользователя.
    - **email**: Электронная почта пользователя.
    - **password**: Пароль пользователя.

    Если пользователь с таким именем уже существует, возвращается ошибка 400.
    """,
    response_description="Возвращает данные созданного пользователя",
)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(**user.model_dump())
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except IntegrityError:
        await db.rollback()  # Откатываем транзакцию
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует",
        )

@app.post(
    "/users/{user_id}/cities/add",
    summary="Добавить город для пользователя",
    description="Добавляет город в список отслеживаемых городов пользователя. "
                "Если город уже существует, связь между пользователем и городом не создается.",
    response_description="Сообщение о результате операции",
    responses={
        200: {"description": "Город успешно добавлен или уже связан с пользователем"},
        404: {"description": "Пользователь не найден"},
    },
)
async def add_city_for_user(
    city: CityCreate,
    user_id: int = Depends(validate_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Проверяем, существует ли пользователь
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверяем, существует ли город
    db_city = await db.execute(select(City).where(City.name == city.name))
    db_city = db_city.scalar_one_or_none()
    if not db_city:
        # Если города нет, создаем его
        db_city = City(**city.model_dump())
        db.add(db_city)
        await db.commit()
        await db.refresh(db_city)

    # Пытаемся добавить связь между пользователем и городом
    stmt = (
        insert(UserCity)
        .values(user_id=user_id, city_id=db_city.id)
        .on_conflict_do_nothing()
    )
    result = await db.execute(stmt)
    await db.commit()

    # Проверяем, была ли добавлена связь
    if result.rowcount == 0:
        return {"message": "City is already linked to the user"}

    return {"message": "City added to user"}

@app.get(
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
    # Проверяем, существует ли пользователь
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получаем города пользователя
    result = await db.execute(
        select(City)
        .join(UserCity, City.id == UserCity.city_id)
        .where(UserCity.user_id == user_id)
    )
    cities = result.scalars().all()

    if not cities:
        raise HTTPException(status_code=404, detail="No cities found for this user")

    return cities

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

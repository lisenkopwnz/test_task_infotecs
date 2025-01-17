from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime, UTC

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
    city_id = Column(Integer, ForeignKey("cities.id"))  # Связь с таблицей городов
    forecast_time = Column(DateTime, nullable=False)    # Время прогноза
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))  # Время записи данных
    temperature = Column(Float)                         # Температура в градусах Цельсия
    humidity = Column(Float)                            # Влажность в процентах
    wind_speed = Column(Float)                          # Скорость ветра в км/ч
    precipitation = Column(Float)                       # Осадки в мм

    __table_args__ = (
        UniqueConstraint('city_id', 'forecast_time', name='uq_city_forecast'),
    )
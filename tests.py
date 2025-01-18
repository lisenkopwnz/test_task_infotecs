import json
import os

import httpx
import pytest
from fastapi import HTTPException
from starlette import status

from file_handlers import CITIES_FILE, USERS_FILE, WEATHER_FILE
from services import get_or_404

BASE_URL = "http://127.0.0.1:8000"

@pytest.fixture(autouse=True)
def cleanup_json_files():
    """
    Фикстура для очистки JSON-файлов после каждого теста.
    """
    yield  # Здесь выполняется тест

    # Очистка JSON-файлов после теста
    for file_path in [CITIES_FILE, USERS_FILE, WEATHER_FILE]:
        if os.path.exists(file_path):
            with open(file_path, "w") as file:
                json.dump({}, file)  # Записываем пустой словарь в файл

@pytest.mark.asyncio
async def test_create_user():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/users",
            json={"username":"test_user"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert  data["username"] == "test_user"

        response = await client.post(
            f"{BASE_URL}/users",
            json={"username": "test_user"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.asyncio
async def test_add_city_for_user():
    async with httpx.AsyncClient() as client:

        response = await client.post(
            f"{BASE_URL}/users",
            json={"username": "test_user_city"}
        )
        assert response.status_code == status.HTTP_200_OK
        user_id = response.json()["id"]

        response = await client.post(
            f"{BASE_URL}/users/{user_id}/cities/add",
            json={"name": "Moscow", "latitude": 55.7558, "longitude": 37.6176}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Город успешно добавлен"

        response = await client.post(
            f"{BASE_URL}/users/{user_id}/cities/add",
            json={"name": "Moscow", "latitude": 55.7558, "longitude": 37.6176}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Пользователь уже добавил этот город"

@pytest.mark.asyncio
async def test_current_weather():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/weather/current-conditions",
            params={"latitude": 55.7558, "longitude": 37.6176}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "temperature" in data
        assert "wind_speed" in data
        assert "pressure" in data

@pytest.mark.asyncio
async def test_get_user_cities():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/users",
            json={"username": "test_user_cities"}
        )
        assert response.status_code == status.HTTP_200_OK
        user_id = response.json()["id"]

        response = await client.post(
            f"{BASE_URL}/users/{user_id}/cities/add",
            json={"name": "Moscow", "latitude": 55.7558, "longitude": 37.6176}
        )
        assert response.status_code == status.HTTP_200_OK

        response = await client.get(
            f"{BASE_URL}/users/{user_id}/cities/"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["name"] == "Moscow"

@pytest.mark.asyncio
async def test_get_weather_at_time():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/users",
            json={"username": "test_user_weather"}
        )
        assert response.status_code == status.HTTP_200_OK
        user_id = response.json()["id"]

        response = await client.post(
            f"{BASE_URL}/users/{user_id}/cities/add",
            json={"name": "Moscow", "latitude": 55.7558, "longitude": 37.6176}
        )
        assert response.status_code == status.HTTP_200_OK

        response = await client.get(
            f"{BASE_URL}/users/{user_id}/weather",
            params={"city_name": "Moscow", "time_str": "12:00", "parameters": "temperature,humidity"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "temperature" in data
        assert "humidity" in data

@pytest.mark.asyncio
async def test_get_or_404_user_exists():
    users_data = {"1": {"username": "test_user"}}
    await get_or_404(1, users_data)

@pytest.mark.asyncio
async def test_get_or_404_user_not_found():
    users_data = {"1": {"username": "test_user"}}
    with pytest.raises(HTTPException) as exc_info:
        await get_or_404(2, users_data)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Пользователь не найден"

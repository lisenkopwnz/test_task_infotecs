import json
from typing import Dict, Any
import aiofiles

USERS_FILE = "users.json"
CITIES_FILE = "cities.json"
WEATHER_FILE = "weather.json"

async def load_data(filename: str) -> Dict[str, Any]:
    """
    Асинхронно загружает данные из JSON-файла.
    """
    async with aiofiles.open(filename, mode="r") as file:
        content = await file.read()
        return json.loads(content)

async def save_data(filename: str, data: Dict[str, Any]):
    """
    Асинхронно сохраняет данные в JSON-файл.
    """
    async with aiofiles.open(filename, mode="w") as file:
        content = json.dumps(data, indent=4)
        await file.write(content)

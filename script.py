import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
from fastapi import FastAPI

import endpoints
from file_handlers import CITIES_FILE, USERS_FILE, WEATHER_FILE
from services import update_weather_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)
task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global task
    # Создаваю файлы, если они не существуют
    for file in [USERS_FILE, CITIES_FILE, WEATHER_FILE]:
        if not Path(file).exists():
            async with aiofiles.open(file, "w") as f:
                await f.write(json.dumps({}))
    logger.info('Запуск приложения')
    # Запускаю задачу обновления прогноза погоды
    task = asyncio.create_task(update_weather_data())
    logger.info('Запуск задачи обновлния погодных данных')
    yield

    # Останавливаем задачу кошда приложение закончило работу
    if task:
        logger.info('Останавливаем задачу')
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info('Отменяем задачу')
        except Exception as e:
            logger.error(f'Ошибка при остановке задачи: {e}')
        finally:
            # Проверяем, есть ли исключение в задаче
            if task.done() and task.exception():
                logger.error(f'Ошибка в задаче: {task.exception()}')

app = FastAPI(lifespan=lifespan)
app.include_router(endpoints.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

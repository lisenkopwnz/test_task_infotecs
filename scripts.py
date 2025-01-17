import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

import endpoints
from database import engine
from models import Base
from services import update_weather_data





@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаем таблицы в базе данных
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Запускаем задачу обновления данных
    task = asyncio.create_task(update_weather_data())

    yield  # Приложение запущено

    # Останавливаем задачу и освобождаем ресурсы
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        await engine.dispose()

app = FastAPI(lifespan=lifespan)

app.include_router(endpoints.router)

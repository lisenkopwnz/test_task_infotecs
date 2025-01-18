# Weather Forecast HTTP Server

HTTP-сервер для предоставления информации о погоде с использованием [Open-Meteo API](https://open-meteo.com/). Реализован на Python с использованием FastAPI.

## Основные методы API

1. **Текущая погода по координатам**:
   - `GET /weather/current?latitude=55.7558&longitude=37.6176`
   - Возвращает: `temperature`, `wind_speed`, `pressure`.

2. **Добавить город**:
   - `POST /cities`
   - Тело запроса (JSON): `{"name": "Moscow", "latitude": 55.7558, "longitude": 37.6176}`

3. **Список городов**:
   - `GET /cities`
   - Возвращает: список городов.

4. **Погода для города на указанное время**:
   - `GET /weather/{city_name}?time=12:00&params=temperature,humidity`
   - Возвращает: запрошенные параметры погоды.

## Дополнительные функции

- **Регистрация пользователя**:
  - `POST /users`
  - Тело запроса (JSON): `{"username": "test_user"}`
  - Возвращает: `id` пользователя.

## Запуск сервера

1. Установите зависимости из файла `requirements.txt`:
   ```bash
   pip install -r requirements.txt

2. Запустите сервер
   ```bash
   python script.py
   
3. Для запуска тестов
   ```bash
   pytest tests.py -v
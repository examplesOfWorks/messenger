# Мессенджер
---
## Оглавление
- [Описание](#описание)
- [Запуск](#запуск)
---
## Описание
Цель – разработать API и web-версию с основными функциями мессенджера.  

<h4 align="center">Функционал раздела "Пользователи":</h4>

- регистрация;
- авторизация;
- получение профиля, как собственного, так и чужого (доступно авторизованным пользователям);
- получения списка пользователей (доступно неавторизованным и авторизованным пользователям).

<h4 align="center">Функционал раздела "Друзья":</h4>

- получение списка собственных друзей;
- отправка другому пользователю заявки в друзья;
- отображение собственных входящих и исходящих заявок в друзья;
- принятие входящей заявки в друзья;
- отклонение входящей заявки в друзья;
- удаление исходящей заявки в друзья.

<h4 align="center">Функционал раздела "Чат":</h4>

- отображение имеющихся диалогов;
- создание диалога с другим пользователем;
- отправка сообщения в указанном диалоге;
- получение переписки в указанном диалоге;
- отображение статусов ("печатает...", "сообщение прочитано/не прочитано", "в сети/не в сети") - доступно только для web-версии;
- отображение счётчиков непрочитанных сообщений;
- отсутствие доступа к диалогу, если пользователь в нём не состоит.

<h4 align="center">Технологии:</h4>

- HTML, CSS, JS, Bootstrap;
- WebSocket;
- python, asyncio, FastAPI;
- PostgreSQL, alembic;
- pytest;
- git, docker.

---
## Запуск

<h4 align="center">Запуск локально (без Docker)</h4>

1)	Клонировать проект в пустую папку
`git clone https://github.com/examplesOfWorks/messenger.git`. 
Перейти в папку messenger.

2)	Создать виртуальное окружение и активировать его
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
```
```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
```

3) Установить зависимости
`pip install -r requirements.txt`

4)	Создать базу данных и её администратора в PostgreSQL используя pgAdmin 4.
Также, если планируется запуск тестов, создать тестового администратора и тестовую базу данных.

5) Создать файл .env в корне проекта со следующим содержимым:

>SECRET_KEY="your-secret-key"
>
>DATABASE_URL=postgresql+asyncpg://db-admin:password@localhost:5432/db-name\
>TEST_DATABASE_URL=postgresql+asyncpg://test-db-admin:test-password@localhost:5432/test-db-name

6) Применить миграции
`alembic upgrade head`

7) Запуск тестов:
`python -m pytest tests`

8) Запуск проекта:
`python main.py`

9) Проект доступен по следующим адресам:
- http://127.0.0.1:8000 - web-версия
- http://localhost:8000/docs или http://localhost:8000/redoc - API

<h4 align="center">Запуск с Docker</h4>

1)	Клонировать проект в пустую папку
```bash
git clone https://github.com/examplesOfWorks/messenger.git
```
Перейти в папку messenger.

2) Создать файл .env в корне проекта со следующим содержимым:

>SECRET_KEY="your-secret-key"
>
>POSTGRES_DB=db-name\
>POSTGRES_USER=db-admin\
>POSTGRES_PASSWORD=password
>
>DOCKER_DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
>
>TEST_POSTGRES_DB=test-db-name\
>TEST_POSTGRES_USER=test-db-admin\
>TEST_POSTGRES_PASSWORD=test-password
>
>TEST_DOCKER_DATABASE_URL=postgresql+asyncpg://${TEST_POSTGRES_USER}:${TEST_POSTGRES_PASSWORD}@db_test:5432/${TEST_POSTGRES_DB}


3) Запуск проекта:
```bash
docker-compose up --build -d
```

4) Запуск тестов:
```bash
docker compose run --rm tests
```

5) Доступ:
- http://127.0.0.1 – сайт
- http://127.0.0.1:8000/docs или http://127.0.0.1:8000/redoc - API
- http://127.0.0.1:8080 – панель администратора. Данные для входа указаны в файле .env. База данных – PostgreSQL

9)	Работа с контейнерами:
```bash
docker compose stop # остановка контейнеров
docker compose start # запуск имеющихся контейнеров
```
или
```bash
docker compose down # остановка удаление контейнеров при сохранении образов и тома
docker compose up -d # создание контейнеров (при имеющихся образах и томе)
```

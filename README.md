# Partner Agent: фронт, Python-бэкенд, auth, RAG и PostgreSQL

Фронт обращается к отдельному FastAPI-бэкенду на порту 8000. Бэкенд проверяет пользователя через auth, сохраняет переписку в PostgreSQL и обращается к внутреннему RAG на порту 8001. Авторизация находится в `services/auth_service`; новый бэкенд — в `services/backend_service`; RAG — в `services/rag_service`.

Все компоненты запускаются из одного `compose.yaml`. PostgreSQL работает отдельным контейнером. В обычной конфигурации наружу открыт только фронт: <http://localhost:8080>. SQLite в работающих сервисах не используется.

## Первый запуск

Нужны Docker Engine / Docker Desktop с Docker Compose v2. Из корня проекта в PowerShell:

```powershell
Copy-Item .env.example .env
# При необходимости измените настройки в .env.
docker compose up -d --build
```

На Linux вместо `Copy-Item` используйте `cp`. Миграции Alembic выполняются при старте auth и бэкенда. PostgreSQL ожидается через healthcheck.

При новом пустом томе Ollama загрузите модели (имена должны совпадать с `.env`):

```powershell
docker compose exec ollama ollama pull qwen3:4b
docker compose exec ollama ollama pull bge-m3
```

Положите тексты компании в `services/rag_service/data/` и выполните индексацию:

```powershell
docker compose exec rag-service python /app/reindex.py
```

Индексация пересоздаёт коллекцию документов. Команда вызывается внутри контейнера; публичного маршрута переиндексации у бэкенда нет. Тексты датасета и файлы моделей в исходном архиве отсутствовали, поэтому они не включены в этот проект.

После этого откройте <http://localhost:8080>, зарегистрируйтесь и задайте вопрос. Логи:

```powershell
docker compose ps
docker compose logs -f backend auth rag-service
```

Для NVIDIA GPU с настроенным NVIDIA Container Toolkit:

```powershell
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

Без дополнительного файла запуск работает на CPU. В auth и бэкенде запущено по одному Uvicorn worker; параллельность Ollama ограничена одним запросом. Два разных диалога могут одновременно обращаться к RAG, а Ollama обрабатывает очередь.

## Если предыдущий RAG уже запускался

Прежний отдельный `services/rag_service/docker-compose.yml` объединён с корневым compose. Остановите прежний стек перед запуском нового, чтобы не держать две копии моделей в памяти. Данные старых Docker volumes автоматически не копируются.

Посмотрите `docker volume ls` и укажите в `.env` **точные существующие имена** томов `OLLAMA_VOLUME_NAME` и `QDRANT_VOLUME_NAME`. Это позволит использовать прежние модели и коллекцию без повторной загрузки. Имена из примера `.env.example` — только пример; Compose мог создать другие имена. Также перенесите исходную папку датасета в `services/rag_service/data/`.

## Где хранится история и как используется контекст

| Данные | Таблица PostgreSQL |
| --- | --- |
| Пользователи, Argon2id-хеши паролей | `auth_users` |
| Сессии, CSRF-токены, время истечения | `auth_sessions` |
| Счётчики попыток входа и регистрации | `auth_rate_limits` |
| Диалоги, владелец, название, текущая генерация | `chat_conversations` |
| Вопросы, ответы, источники, порядок, статусы | `chat_messages` |
| Версии схем auth и бэкенда | `auth_schema_version`, `backend_schema_version` |

Данные PostgreSQL хранятся в постоянном томе `partner-agent_postgres_data` (имя можно задать через `POSTGRES_VOLUME_NAME`). Обычные `docker compose restart`, `down` и повторный `up` его сохраняют. `down -v` удаляет тома и данные.

При выходе удаляется сессия, а переписка остаётся. После повторного входа, обновления страницы и входа из другого браузера фронт получает те же диалоги через API. В браузерное хранилище переписка больше не записывается.

Владелец определяется бэкендом по проверенной сессии. Чужой диалог возвращает 404 при чтении, отправке вопроса, остановке и удалении. История от клиента не принимается: для продолжения передаётся `conversation_id`, а предыдущие сообщения бэкенд читает из БД самостоятельно.

В контекст попадают последние завершённые пары «вопрос → ответ» **только выбранного диалога**. По умолчанию это до 10 пар и до 12 000 символов; параметры `HISTORY_TURNS` и `HISTORY_MAX_CHARS` задаются в `.env`. RAG получает до 20 сообщений (`RAG_HISTORY_LIMIT`) при окне модели `NUM_CTX=8192`. Вся переписка сохраняется в БД, даже когда старые сообщения выходят за пределы окна контекста. При изменении лимитов согласуйте размер истории с окном модели.

Для поиска документов RAG учитывает также последние два пользовательских вопроса — это помогает с уточнениями вроде «А какие там условия?». При формировании ответа он получает сохранённую историю диалога. Ограничение ответа фактами документов компании сохранено.

Вопрос и пустой ответ со статусом `streaming` создаются до обращения к RAG. Источники и промежуточный текст сохраняются во время потока; окончательный ответ фиксируется перед событием `done`. При обрыве соединения, ошибке и остановке остаётся частичный текст со статусом `cancelled` или `error`. Такие пары исключаются из следующего контекста. При аварийном завершении процесса незавершённый ответ восстанавливается как `cancelled` после истечения блокировки (таймаут генерации + 30 секунд), при следующем открытии диалога или новом вопросе.

В одном диалоге разрешена одна активная генерация. Повтор уже завершённого запроса с тем же `request_id` возвращает сохранённый ответ, не создавая дубли и не вызывая RAG повторно. Для повторной попытки после ошибки фронт создаёт новый `request_id`, сохраняя прежнюю неудачную попытку в истории.

История прежней версии существовала только в `sessionStorage` вкладки и очищалась при выходе. В исходном архиве её нет; автоматического переноса этой старой браузерной истории нет.

## Перенос старой авторизации из SQLite

В присланном архиве файла `auth.db` нет. Новый запуск создаёт PostgreSQL и пустую схему. Чтобы перенести реальные прежние аккаунты, выполните импорт своей базы.

**До замены старого проекта**, если использовалась стандартная SQLite `/app/data/auth.db`, сделайте согласованную копию через SQLite backup API:

```powershell
New-Item -ItemType Directory -Force legacy
docker compose exec auth python -c "import sqlite3; s=sqlite3.connect('/app/data/auth.db'); d=sqlite3.connect('/tmp/auth-backup.db'); s.backup(d); d.close(); s.close()"
docker compose cp auth:/tmp/auth-backup.db ./legacy/auth.db
```

Так в копию попадут и зафиксированные данные WAL. Остановите прежнюю авторизацию до импорта, чтобы после копирования в ней не появлялись новые пользователи и сессии. Перенесите `legacy/auth.db` в корень обновлённого проекта. Если файл лежит в другом месте, укажите `SQLITE_AUTH_PATH` в `.env`.

В обновлённом проекте, **перед регистрациями пользователей в новом auth**:

```powershell
docker compose up -d postgres
docker compose -f compose.yaml -f compose.migrate.yaml build auth
# Прочитать исходную базу и показать количество строк, без записи данных.
docker compose -f compose.yaml -f compose.migrate.yaml run --rm --no-deps auth python -m app.migrate_sqlite --source /legacy/auth.db --dry-run
# Создать схему и перенести данные.
docker compose -f compose.yaml -f compose.migrate.yaml run --rm --no-deps auth python -m app.migrate_sqlite --source /legacy/auth.db
docker compose up -d --build
```

Импорт переносит `auth_users`, `auth_sessions`, `auth_rate_limits`, сохраняя идентификаторы, хеши паролей, CSRF и действующие сессии. SQLite открывается только для чтения. Все строки переносятся одной транзакцией PostgreSQL. Повторный импорт идентичных строк допускается; конфликт идентификатора, email или содержимого останавливает импорт с откатом перенесённых строк. Старый файл и Docker volume до проверки переноса сохраните.

Если старую регистрацию уже использовали и в новой базе появились несовпадающие записи, автоматическое объединение аккаунтов не выполняется.

## HTTP API

Через Nginx `/api/v1/auth/*` идёт в auth, остальные `/api/v1/*` — в бэкенд. Дополнительная проверка auth в Nginx больше не нужна: бэкенд проверяет сессию самостоятельно на каждом защищённом запросе.

| Метод | Маршрут | Назначение |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Регистрация и сессия |
| POST | `/api/v1/auth/login` | Вход |
| GET | `/api/v1/auth/me` | Пользователь, CSRF, срок сессии |
| POST | `/api/v1/auth/logout` | Отзыв сессии |
| GET | `/api/v1/conversations?limit=100&offset=0` | Список своих диалогов, без сообщений |
| POST | `/api/v1/conversations` | Создать диалог, тело `{"title":"Новый диалог"}` |
| GET | `/api/v1/conversations/{id}` | Диалог со всеми сообщениями |
| DELETE | `/api/v1/conversations/{id}` | Удалить диалог и сообщения |
| POST | `/api/v1/conversations/{id}/requests/{request_id}/cancel` | Остановить запрос |
| POST | `/api/v1/ask` | Получить и сохранить полный ответ |
| POST | `/api/v1/ask/stream` | Получить и сохранить ответ через SSE |
| GET | `/api/v1/documents` | Документы RAG |
| GET | `/api/v1/docs` | Swagger бэкенда |

Пример запроса бэкенду:

```json
{
  "conversation_id": "UUID существующего своего диалога",
  "request_id": "новый UUID запроса",
  "question": "А какие условия обучения?"
}
```

`request_id` необязателен для API, но фронт всегда задаёт его для повтора и остановки. Поля `user_id` и `history` в этом контракте запрещены. Внутренний контракт RAG остаётся прежним: `{"question":"...","history":[{"role":"user","content":"..."}]}`.

SSE бэкенда передаёт `meta` (ID диалога, запроса и сообщений), `sources`, `token`, `done`; при ошибке — `error` без `done`. В `sources` бэкенд добавляет стабильный `doc_id` по имени источника, поскольку RAG присылает только `source` и `score`.

Сессия — HttpOnly-cookie `partner_session`, срок 7 дней. Для изменяющих запросов нужны `X-Requested-With: PartnerAgent`, `X-CSRF-Token` из `/auth/me` и разрешённый Origin. Вход и регистрация не требуют CSRF, но требуют `X-Requested-With`. Cookie передаётся с `credentials: include`. Пароль и идентификатор cookie не возвращаются в JSON.

## Локальная разработка и DBeaver

Дополнительный файл открывает порты сервисов только на `127.0.0.1`:

```powershell
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

DBeaver: `localhost:5432`, база/пользователь/пароль из `.env`. Auth: `localhost:8002`, бэкенд: `localhost:8000`, RAG: `localhost:8001`. Swagger также доступен через фронт: <http://localhost:8080/api/v1/docs>.

Чтобы запускать Python-сервисы из IDE, задайте им `DATABASE_URL=postgresql+psycopg://partner:partner_local_password@127.0.0.1:5432/partner`. Бэкенду также нужны `AUTH_URL=http://127.0.0.1:8002` и `RAG_URL=http://127.0.0.1:8001`. Переменные среды задаются в конфигурации запуска IDE / терминале; обычный `uvicorn` auth и бэкенда не читает корневой `.env` автоматически.

Из каталога каждого Python-сервиса:

```powershell
python -m pip install -r requirements.txt
python -m app.migrate
python -m uvicorn app.main:app --port 8002
# Для backend_service используйте --port 8000.
```

На Windows для локального async psycopg может понадобиться цикл Selector. Самый простой проверяемый способ запуска бэкенда — контейнер из compose.

Фронт:

```powershell
cd frontend
npm ci
npm run dev
```

Vite проксирует auth на 8002, бэкенд на 8000. Публичные адреса меняются через `frontend/.env.example`. Для HTTPS задайте `COOKIE_SECURE=true` и точные origin в `ALLOWED_ORIGINS`. Перед публичным размещением замените пример пароля PostgreSQL.

## Проверки

Python-тестам нужна PostgreSQL; они создают и удаляют отдельные временные схемы. Установите зависимости auth и бэкенда в тестовое окружение, выполните `npm ci` во фронте и задайте `TEST_DATABASE_URL` для своей тестовой БД. Затем из корня:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://partner:partner_local_password@127.0.0.1:5432/partner"
python scripts/test.py
```

Тесты охватывают авторизацию, сохранение сессий, SQLite → PostgreSQL, откат конфликтов, хранение истории и источников, повтор запросов, изоляцию пользователей и диалогов, параллельные запросы, остановку, ошибки/обрывы/таймауты RAG и восстановление после перезапуска.

Подробные результаты проверки этой версии — в `VALIDATION.md`.

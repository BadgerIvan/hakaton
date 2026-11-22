# Partner Agent: фронт, Python-бэкенд, auth, RAG и PostgreSQL

Фронт обращается к отдельному FastAPI-бэкенду на порту 8000. Бэкенд проверяет пользователя через auth, сохраняет переписку в PostgreSQL и обращается к внутреннему RAG на порту 8001. Авторизация находится в `services/auth_service`; бэкенд - в `services/backend_service`; RAG - в `services/rag_service`.

Все компоненты запускаются из одного `compose.yaml`. В обычной конфигурации наружу открыт только фронт: <http://localhost:8080>.

## Первый запуск

Нужен Docker Engine с Docker Compose v2. Из корня проекта:

```bash
cp .env.example .env
# При необходимости измените настройки в .env.
docker compose up -d --build
```

При новом пустом томе Ollama загрузите модели (имена должны совпадать с `.env`):

```bash
docker compose exec ollama ollama pull qwen3:4b-instruct-2507-q4_K_M
docker compose exec ollama ollama pull bge-m3
```

Загрузите `.md`/`.txt` через <http://localhost:8080/admin> с токеном `RAG_ADMIN_TOKEN`. Для массовой загрузки подготовьте `services/rag_service/data/`, скопируйте её в именованный том и выполните индексацию:

```bash
docker compose cp ./services/rag_service/data/. rag-service:/app/data/
docker compose exec rag-service python /app/reindex.py
```

Индексация пересоздаёт коллекцию документов. Команда вызывается внутри контейнера; публичного маршрута переиндексации у бэкенда нет. Тексты датасета и файлы моделей в исходном архиве отсутствовали, поэтому они не включены в этот проект.

После этого откройте <http://localhost:8080>, зарегистрируйтесь и задайте вопрос. Логи:

```bash
docker compose ps
docker compose logs -f backend auth rag-service
```

Для NVIDIA GPU с настроенным NVIDIA Container Toolkit:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

Без дополнительного файла запуск работает на CPU. В auth и бэкенде запущено по одному Uvicorn worker; параллельность Ollama ограничена одним запросом. Два разных диалога могут одновременно обращаться к RAG, а Ollama обрабатывает очередь.


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

При выходе удаляется сессия, а переписка остаётся. После повторного входа, обновления страницы и входа из другого браузера фронт получает те же диалоги через API.

Владелец определяется бэкендом по проверенной сессии. Чужой диалог возвращает 404 при чтении, отправке вопроса, остановке и удалении. История от клиента не принимается: для продолжения передаётся `conversation_id`, а предыдущие сообщения бэкенд читает из БД самостоятельно.

В контекст попадают последние завершённые пары «вопрос - ответ» **только выбранного диалога**. По умолчанию это до 10 пар и до 12 000 символов; параметры `HISTORY_TURNS` и `HISTORY_MAX_CHARS` задаются в `.env`. RAG формирует компактный контекст из последних шести очищенных сообщений (до 2400 символов) при окне модели `NUM_CTX=8192`. Вся переписка сохраняется в БД, даже когда старые сообщения выходят за пределы окна контекста. При изменении лимитов согласуйте размер истории с окном модели.

Для поиска документов RAG переписывает запрос с учётом последних четырёх очищенных сообщений - это помогает с уточнениями вроде «А какие там условия?». При формировании ответа он получает сохранённую историю диалога. Ограничение ответа фактами документов компании сохранено.

## HTTP API

Через Nginx `/api/v1/auth/*` идёт в auth, остальные `/api/v1/*` - в бэкенд. Дополнительная проверка auth в Nginx больше не нужна: бэкенд проверяет сессию самостоятельно на каждом защищённом запросе.

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

SSE бэкенда передаёт `meta` (ID диалога, запроса и сообщений), `sources`, `token`, `done`; при ошибке - `error` без `done`. В `sources` бэкенд добавляет стабильный `doc_id` по имени источника, поскольку RAG присылает только `source` и `score`.

Сессия - HttpOnly-cookie `partner_session`, срок 7 дней. Для изменяющих запросов нужны `X-Requested-With: PartnerAgent`, `X-CSRF-Token` из `/auth/me` и разрешённый Origin. Вход и регистрация не требуют CSRF, но требуют `X-Requested-With`. Cookie передаётся с `credentials: include`. Пароль и идентификатор cookie не возвращаются в JSON.

## Логи и тесты

```bash
python -m pip install -r requirements-test.txt
npm --prefix frontend ci
python scripts/test.py --unit --coverage
# Отдельный стенд с PostgreSQL/Qdrant и сквозным API-тестом:
python scripts/test-stack.py
```
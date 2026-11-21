import hashlib
import hmac
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .database import Base, RateLimit, User, UserSession, build_engine

password_hasher = PasswordHasher()


class Credentials(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return str(value).lower()


class Registration(Credentials):
    name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Пароль не может состоять только из пробелов")
        return value


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str


class SessionView(BaseModel):
    user: UserView
    csrf_token: str
    expires_at: str


def get_database(request: Request):
    with request.app.state.sessions() as database:
        yield database


Database = Annotated[Session, Depends(get_database)]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def require_session(request: Request, database: Database) -> UserSession:
    token = request.cookies.get(request.app.state.settings.cookie_name, "")
    if not token or len(token) > 256:
        raise HTTPException(401, "Войдите в аккаунт")
    session = database.get(UserSession, digest(token))
    if session is None or session.expires_at <= int(time.time()):
        raise HTTPException(401, "Сессия завершилась. Войдите ещё раз")
    return session


CurrentSession = Annotated[UserSession, Depends(require_session)]


def consume_limit(
    database: Session, scope: str, value: str, limit: int, settings: Settings
):
    now = int(time.time())
    window = now // settings.rate_window_seconds
    expires = (window + 1) * settings.rate_window_seconds
    key = digest(f"{scope}:{value}:{window}")
    insert = (
        sqlite_insert if database.bind.dialect.name == "sqlite" else postgres_insert
    )
    statement = insert(RateLimit).values(key=key, count=1, expires_at=expires)
    statement = statement.on_conflict_do_update(
        index_elements=[RateLimit.key], set_={"count": RateLimit.count + 1}
    ).returning(RateLimit.count)
    count = database.execute(statement).scalar_one()
    database.execute(delete(RateLimit).where(RateLimit.expires_at < now))
    database.commit()
    if count > limit:
        raise HTTPException(
            429,
            "Слишком много попыток. Попробуйте позже",
            headers={"Retry-After": str(expires - now)},
        )


def issue_session(request: Request, response: Response, database: Session, user: User):
    settings = request.app.state.settings
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    session = UserSession(
        token_hash=digest(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now + settings.session_days * 86400,
    )
    previous = request.cookies.get(settings.cookie_name)
    if previous:
        database.execute(
            delete(UserSession).where(UserSession.token_hash == digest(previous))
        )
    database.execute(delete(UserSession).where(UserSession.expires_at <= now))
    database.add(session)
    database.commit()
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return session_view(user, session)


def session_view(user: User, session: UserSession) -> SessionView:
    return SessionView(
        user=UserView.model_validate(user),
        csrf_token=session.csrf_token,
        expires_at=datetime.fromtimestamp(session.expires_at, timezone.utc).isoformat(),
    )


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        Base.metadata.create_all(engine)
        application.state.dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
        yield
        engine.dispose()

    application = FastAPI(
        title="Partner Agent Auth", version="1.0.0", lifespan=lifespan
    )
    application.state.settings = settings
    application.state.sessions = sessionmaker(engine, expire_on_commit=False)

    @application.middleware("http")
    async def protect_auth_requests(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in settings.allowed_origins:
                return JSONResponse(
                    {"detail": "Источник запроса не разрешён"}, status_code=403
                )
            if request.headers.get("x-requested-with") != "PartnerAgent":
                return JSONResponse(
                    {"detail": "Необходим заголовок X-Requested-With"}, status_code=403
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Requested-With"],
    )

    @application.get("/health")
    def health(database: Database):
        database.execute(text("SELECT 1"))
        return {"status": "ok"}

    @application.post(
        "/api/v1/auth/register", response_model=SessionView, status_code=201
    )
    def register(
        body: Registration, request: Request, response: Response, database: Database
    ):
        client_ip = request.client.host if request.client else "unknown"
        consume_limit(
            database, "register-ip", client_ip, settings.register_ip_limit, settings
        )
        user = User(
            id=str(uuid4()),
            name=body.name,
            email=str(body.email),
            password_hash=password_hasher.hash(body.password),
            created_at=int(time.time()),
        )
        database.add(user)
        try:
            database.flush()
            return issue_session(request, response, database, user)
        except IntegrityError:
            database.rollback()
            raise HTTPException(409, "Аккаунт с такой почтой уже существует") from None

    @application.post("/api/v1/auth/login", response_model=SessionView)
    def login(
        body: Credentials, request: Request, response: Response, database: Database
    ):
        client_ip = request.client.host if request.client else "unknown"
        consume_limit(
            database, "login-ip", client_ip, settings.login_ip_limit, settings
        )
        consume_limit(
            database,
            "login-email",
            str(body.email),
            settings.login_email_limit,
            settings,
        )
        user = database.scalar(select(User).where(User.email == str(body.email)))
        stored_hash = user.password_hash if user else request.app.state.dummy_hash
        try:
            password_hasher.verify(stored_hash, body.password)
        except (VerificationError, InvalidHashError):
            raise HTTPException(401, "Неверная почта или пароль") from None
        if user is None:
            raise HTTPException(401, "Неверная почта или пароль")
        if password_hasher.check_needs_rehash(user.password_hash):
            user.password_hash = password_hasher.hash(body.password)
        return issue_session(request, response, database, user)

    @application.get("/api/v1/auth/me", response_model=SessionView)
    def me(session: CurrentSession, database: Database):
        user = database.get(User, session.user_id)
        if user is None:
            raise HTTPException(401, "Войдите в аккаунт")
        return session_view(user, session)

    @application.post("/api/v1/auth/logout", status_code=204)
    def logout(
        request: Request,
        response: Response,
        session: CurrentSession,
        database: Database,
    ):
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not hmac.compare_digest(
            csrf.encode(), session.csrf_token.encode()
        ):
            raise HTTPException(403, "Обновите страницу и повторите выход")
        database.delete(session)
        database.commit()
        response.delete_cookie(
            settings.cookie_name,
            path="/",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )

    return application


app = create_app()

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import os
import time
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .database import Base, SessionLocal, engine, get_db
from .models import Game, Purchase, PurchaseItem, User
from .schemas import (
    AdminUserCreate,
    GameCreate,
    GameOut,
    GameUpdate,
    HealthOut,
    LoginRequest,
    PurchaseCreate,
    PurchaseOut,
    TokenOut,
    UserOut,
    UserUpdate,
)
from .security import create_access_token, get_current_user, hash_password, require_admin, verify_password
from .telemetry import configure_json_logging, logger_provider, observe_request

configure_json_logging()
logger = logging.getLogger("compra_juegos")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    try:
        yield
    finally:
        shutdown_telemetry()


app = FastAPI(title="CompraJuegos API", version="1.0.0", lifespan=lifespan)
allowed_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:4200,http://localhost:8080"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        logger.exception("Unhandled request exception", extra={"http_method": request.method})
        raise
    finally:
        elapsed = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", request.url.path)
        observe_request(request.method, route, status_code, elapsed)
        logger.info(
            "HTTP request",
            extra={
                "http_method": request.method,
                "http_route": route,
                "status_code": status_code,
                "response_time_ms": round(elapsed * 1000, 2),
            },
        )


def seed_data(db: Session) -> None:
    if db.scalar(select(func.count(Game.id))) == 0:
        db.add_all(
            [
                Game(
                    title="Aventura en Hyrule",
                    description="Explora un reino abierto, resuelve acertijos y descubre secretos.",
                    platform="Nintendo Switch",
                    category="Aventura",
                    price=Decimal("1199.00"),
                    image_url="https://images.unsplash.com/photo-1607853202273-797f1c22a38e?auto=format&fit=crop&w=800&q=80",
                    stock=25,
                ),
                Game(
                    title="Carrera Neon",
                    description="Compite a toda velocidad en pistas futuristas llenas de neón.",
                    platform="PlayStation 5",
                    category="Carreras",
                    price=Decimal("899.00"),
                    image_url="https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=800&q=80",
                    stock=18,
                ),
                Game(
                    title="Leyendas del Dragón",
                    description="Forma tu equipo, domina la magia y derrota al dragón antiguo.",
                    platform="PC",
                    category="RPG",
                    price=Decimal("749.00"),
                    image_url="https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=800&q=80",
                    stock=30,
                ),
                Game(
                    title="Operación Horizonte",
                    description="Coordina a tu escuadrón en misiones tácticas cooperativas.",
                    platform="Xbox Series X",
                    category="Acción",
                    price=Decimal("999.00"),
                    image_url="https://images.unsplash.com/photo-1493711662062-fa541adb3fc8?auto=format&fit=crop&w=800&q=80",
                    stock=12,
                ),
            ]
        )
    admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if bool(admin_email) != bool(admin_password):
        raise RuntimeError("Configura BOOTSTRAP_ADMIN_EMAIL y BOOTSTRAP_ADMIN_PASSWORD juntos")
    if admin_email and db.scalar(select(User).where(User.email == admin_email)) is None:
        db.add(
            User(
                email=admin_email,
                full_name="Administrador",
                password_hash=hash_password(admin_password),
                role="admin",
            )
        )
    db.commit()


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        user_columns = {column["name"] for column in inspect(connection).get_columns("users")}
        if "is_active" not in user_columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
            )
    with SessionLocal() as db:
        seed_data(db)


def database_error() -> HTTPException:
    return HTTPException(status_code=409, detail="El correo ya está registrado")


@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health() -> HealthOut:
    return HealthOut(status="ok")


@app.post("/api/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: AdminUserCreate, db: Session = Depends(get_db)) -> User:
    user = User(
        email=str(payload.email).lower(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="customer",
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise database_error()
    return user


@app.post("/api/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="La cuenta está dada de baja")
    return TokenOut(access_token=create_access_token(user), user=user)


@app.get("/api/auth/me", response_model=UserOut)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user


@app.get("/api/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id).limit(limit)).all())


@app.post("/api/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> User:
    user = User(
        email=str(payload.email).lower(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise database_error()
    return user


@app.patch("/api/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if (
        user.role == "admin"
        and user.is_active
        and (changes.get("role") == "customer" or changes.get("is_active") is False)
        and db.scalar(
            select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))
        )
        <= 1
    ):
        raise HTTPException(status_code=400, detail="Debe quedar al menos un administrador")
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).lower()
    if "full_name" in changes and changes["full_name"] is not None:
        changes["full_name"] = changes["full_name"].strip()
    if "password" in changes and changes["password"] is not None:
        changes["password_hash"] = hash_password(changes.pop("password"))
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise database_error()
    return user


@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> Response:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not user.is_active:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if user.role == "admin" and db.scalar(
        select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))
    ) <= 1:
        raise HTTPException(status_code=400, detail="Debe quedar al menos un administrador")
    user.is_active = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/games", response_model=list[GameOut])
def list_games(
    db: Session = Depends(get_db),
    category: str | None = None,
    search: str | None = Query(default=None, max_length=120),
) -> list[Game]:
    query = select(Game).order_by(Game.id)
    if category:
        query = query.where(Game.category == category)
    if search:
        query = query.where(Game.title.ilike(f"%{search.strip()}%"))
    return list(db.scalars(query).all())


@app.get("/api/games/{game_id}", response_model=GameOut)
def get_game(game_id: int, db: Session = Depends(get_db)) -> Game:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    return game


@app.post("/api/games", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def create_game(
    payload: GameCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> Game:
    game = Game(**payload.model_dump())
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


@app.patch("/api/games/{game_id}", response_model=GameOut)
def update_game(
    game_id: int,
    payload: GameUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Game:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(game, field, value)
    db.commit()
    db.refresh(game)
    return game


@app.delete("/api/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(
    game_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> Response:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    if game.purchase_items:
        raise HTTPException(status_code=409, detail="No se puede eliminar un juego ya vendido")
    db.delete(game)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/purchases", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    payload: PurchaseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Purchase:
    quantities: dict[int, int] = {}
    for item in payload.items:
        quantities[item.game_id] = quantities.get(item.game_id, 0) + item.quantity
    games = {
        game.id: game
        for game in db.scalars(select(Game).where(Game.id.in_(quantities))).all()
    }
    if len(games) != len(quantities):
        raise HTTPException(status_code=404, detail="Uno o más juegos no existen")
    for game_id, quantity in quantities.items():
        if games[game_id].stock < quantity:
            raise HTTPException(status_code=409, detail=f"Existencias insuficientes: {games[game_id].title}")
    total = sum((games[game_id].price * quantity for game_id, quantity in quantities.items()), Decimal("0"))
    purchase = Purchase(user_id=user.id, total=total, status="confirmed")
    db.add(purchase)
    db.flush()
    for game_id, quantity in quantities.items():
        changed = db.execute(
            update(Game)
            .where(Game.id == game_id, Game.stock >= quantity)
            .values(stock=Game.stock - quantity)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Las existencias cambiaron; intenta de nuevo")
        game = games[game_id]
        purchase.items.append(
            PurchaseItem(
                game_id=game_id,
                game_title=game.title,
                quantity=quantity,
                unit_price=game.price,
            )
        )
    db.commit()
    return db.scalar(
        select(Purchase).options(selectinload(Purchase.items)).where(Purchase.id == purchase.id)
    )


@app.get("/api/purchases", response_model=list[PurchaseOut])
def list_purchases(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Purchase]:
    return list(
        db.scalars(
            select(Purchase)
            .options(selectinload(Purchase.items))
            .where(Purchase.user_id == user.id)
            .order_by(Purchase.created_at.desc())
        ).all()
    )


def shutdown_telemetry() -> None:
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry import metrics, trace

        trace.get_tracer_provider().force_flush()
        metrics.get_meter_provider().force_flush()
        if logger_provider is not None:
            logger_provider.force_flush()


if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="/api/health")
    SQLAlchemyInstrumentor().instrument(engine=engine)

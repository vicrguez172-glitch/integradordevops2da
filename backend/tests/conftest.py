import os

os.environ.setdefault("SECRET_KEY", "pytest-secret-key-that-is-long-enough")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def admin_token(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "admin@example.com", "full_name": "Admin User", "password": "secure-pass-123"},
    )
    assert response.status_code == 201
    from app.database import get_db
    from app.models import User

    override = app.dependency_overrides[get_db]
    db = next(override())
    admin = db.query(User).filter_by(email="admin@example.com").one()
    admin.role = "admin"
    db.commit()
    db.close()
    response = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "secure-pass-123"}
    )
    return response.json()["access_token"]

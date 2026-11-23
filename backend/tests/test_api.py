def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_current_user(client):
    registered = client.post(
        "/api/auth/register",
        json={"email": "buyer@example.com", "full_name": "Game Buyer", "password": "password-123"},
    )
    assert registered.status_code == 201
    assert "password_hash" not in registered.json()
    assert registered.json()["is_active"] is True
    logged_in = client.post(
        "/api/auth/login", json={"email": "buyer@example.com", "password": "password-123"}
    )
    assert logged_in.status_code == 200
    current = client.get("/api/auth/me", headers=auth(logged_in.json()["access_token"]))
    assert current.json()["email"] == "buyer@example.com"


def test_passwords_must_have_at_least_eight_characters(client, admin_token):
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "short-password@example.com",
            "full_name": "Short Password",
            "password": "short",
        },
    )
    assert registration.status_code == 422

    admin = next(
        user for user in client.get("/api/users", headers=auth(admin_token)).json()
        if user["email"] == "admin@example.com"
    )
    update = client.patch(
        f"/api/users/{admin['id']}",
        headers=auth(admin_token),
        json={"password": "short"},
    )
    assert update.status_code == 422


def test_admin_can_manage_users_and_regular_user_cannot(client, admin_token):
    denied = client.get("/api/users")
    assert denied.status_code == 401
    created = client.post(
        "/api/users",
        headers=auth(admin_token),
        json={"email": "new@example.com", "full_name": "New User", "password": "password-123"},
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    user_token = client.post(
        "/api/auth/login", json={"email": "new@example.com", "password": "password-123"}
    ).json()["access_token"]
    updated = client.patch(
        f"/api/users/{user_id}", headers=auth(admin_token), json={"full_name": "Updated User"}
    )
    assert updated.json()["full_name"] == "Updated User"
    deleted = client.delete(f"/api/users/{user_id}", headers=auth(admin_token))
    assert deleted.status_code == 204
    inactive_user = next(
        user for user in client.get("/api/users", headers=auth(admin_token)).json()
        if user["id"] == user_id
    )
    assert inactive_user["is_active"] is False
    assert client.post(
        "/api/auth/login", json={"email": "new@example.com", "password": "password-123"}
    ).status_code == 403
    assert client.get("/api/auth/me", headers=auth(user_token)).status_code == 401
    reactivated = client.patch(
        f"/api/users/{user_id}", headers=auth(admin_token), json={"is_active": True}
    )
    assert reactivated.json()["is_active"] is True


def test_admin_can_create_admin_and_last_admin_cannot_be_demoted(client, admin_token):
    admin_headers = auth(admin_token)
    initial_admin = client.get("/api/users", headers=admin_headers).json()[0]

    blocked_demotion = client.patch(
        f"/api/users/{initial_admin['id']}",
        headers=admin_headers,
        json={"role": "customer"},
    )
    assert blocked_demotion.status_code == 400
    assert blocked_demotion.json()["detail"] == "Debe quedar al menos un administrador"
    blocked_deactivation = client.delete(
        f"/api/users/{initial_admin['id']}", headers=admin_headers
    )
    assert blocked_deactivation.status_code == 400

    created = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "second-admin@example.com",
            "full_name": "Second Admin",
            "password": "password-123",
            "role": "admin",
        },
    )
    assert created.status_code == 201
    assert created.json()["role"] == "admin"

    second_admin_token = client.post(
        "/api/auth/login",
        json={"email": "second-admin@example.com", "password": "password-123"},
    ).json()["access_token"]
    demoted = client.patch(
        f"/api/users/{initial_admin['id']}",
        headers=auth(second_admin_token),
        json={"role": "customer"},
    )
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "customer"

    updated_admin = client.patch(
        f"/api/users/{created.json()['id']}",
        headers=auth(second_admin_token),
        json={"email": "updated-admin@example.com", "password": "updated-password-123"},
    )
    assert updated_admin.status_code == 200
    assert updated_admin.json()["email"] == "updated-admin@example.com"
    relogin = client.post(
        "/api/auth/login",
        json={"email": "updated-admin@example.com", "password": "updated-password-123"},
    )
    assert relogin.status_code == 200


def test_catalog_admin_crud_and_checkout_updates_stock(client, admin_token):
    game = client.post(
        "/api/games",
        headers=auth(admin_token),
        json={
            "title": "Juego de prueba",
            "description": "Un juego de aventuras para la prueba.",
            "platform": "PC",
            "category": "Aventura",
            "price": "250.00",
            "image_url": "https://example.com/game.jpg",
            "stock": 5,
        },
    )
    assert game.status_code == 201
    game_id = game.json()["id"]
    assert client.get("/api/games").status_code == 200
    assert client.patch(
        f"/api/games/{game_id}", headers=auth(admin_token), json={"price": "200.00"}
    ).json()["price"] == "200.00"

    buyer = client.post(
        "/api/auth/register",
        json={"email": "buyer@example.com", "full_name": "Buyer", "password": "password-123"},
    ).json()
    token_response = client.post(
        "/api/auth/login", json={"email": buyer["email"], "password": "password-123"}
    )
    buyer_token = token_response.json()["access_token"]
    purchase = client.post(
        "/api/purchases",
        headers=auth(buyer_token),
        json={"items": [{"game_id": game_id, "quantity": 2}]},
    )
    assert purchase.status_code == 201
    assert purchase.json()["total"] == "400.00"
    assert client.get(f"/api/games/{game_id}").json()["stock"] == 3
    assert len(client.get("/api/purchases", headers=auth(buyer_token)).json()) == 1
    deactivated = client.delete(f"/api/users/{buyer['id']}", headers=auth(admin_token))
    assert deactivated.status_code == 204
    buyer_record = next(
        user for user in client.get("/api/users", headers=auth(admin_token)).json()
        if user["id"] == buyer["id"]
    )
    assert buyer_record["is_active"] is False
    assert client.post(
        "/api/auth/login", json={"email": buyer["email"], "password": "password-123"}
    ).status_code == 403
    from app.database import get_db
    from app.main import app
    from app.models import Purchase

    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.query(Purchase).filter_by(user_id=buyer["id"]).count() == 1
    finally:
        db.close()


def test_checkout_rejects_insufficient_stock_without_partial_purchase(client, admin_token):
    game = client.post(
        "/api/games",
        headers=auth(admin_token),
        json={
            "title": "Existencias limitadas",
            "description": "Juego con pocas existencias disponibles.",
            "platform": "PC",
            "category": "RPG",
            "price": "50.00",
            "image_url": "https://example.com/game.jpg",
            "stock": 1,
        },
    ).json()
    buyer = client.post(
        "/api/auth/register",
        json={"email": "buyer@example.com", "full_name": "Buyer", "password": "password-123"},
    ).json()
    token = client.post(
        "/api/auth/login", json={"email": buyer["email"], "password": "password-123"}
    ).json()["access_token"]
    response = client.post(
        "/api/purchases",
        headers=auth(token),
        json={"items": [{"game_id": game["id"], "quantity": 2}]},
    )
    assert response.status_code == 409
    assert client.get(f"/api/games/{game['id']}").json()["stock"] == 1
    assert client.get("/api/purchases", headers=auth(token)).json() == []

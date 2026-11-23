from uuid import uuid4

import pytest


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def new_game_payload(title: str) -> dict[str, object]:
    return {
        "title": title,
        "description": "Un juego preparado para verificar todos los endpoints.",
        "platform": "PC",
        "category": "Aventura",
        "price": "250.00",
        "image_url": "https://example.com/endpoint-test.jpg",
        "stock": 5,
    }


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_registration_accepts_unicode_names_special_passwords_and_uppercase_email(client):
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "Jose+Jugador@Example.COM",
            "full_name": "José O'Connor-Smith",
            "password": "Áventura!2026",
        },
    )
    assert registration.status_code == 201
    assert registration.json()["email"] == "jose+jugador@example.com"
    assert registration.json()["full_name"] == "José O'Connor-Smith"
    assert client.post(
        "/api/auth/login",
        json={"email": "JOSE+JUGADOR@EXAMPLE.COM", "password": "Áventura!2026"},
    ).status_code == 200


def test_authentication_endpoint_success_failure_and_duplicate_email(client):
    suffix = uuid4().hex
    credentials = {
        "email": f"auth-{suffix}@example.com",
        "full_name": "Endpoint Buyer",
        "password": "secure-password-123",
    }

    registered = client.post("/api/auth/register", json=credentials)
    assert registered.status_code == 201
    assert registered.json()["role"] == "customer"
    assert "password_hash" not in registered.json()
    assert client.post("/api/auth/register", json=credentials).status_code == 409

    assert client.post(
        "/api/auth/login",
        json={"email": credentials["email"], "password": "incorrect-password"},
    ).status_code == 401
    token_response = client.post(
        "/api/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    current_user = client.get("/api/auth/me", headers=auth(token))
    assert current_user.status_code == 200
    assert current_user.json()["email"] == credentials["email"]
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth("invalid-token")).status_code == 401


def test_user_endpoints_cover_authorization_crud_and_reactivation(client, admin_token):
    admin_headers = auth(admin_token)
    suffix = uuid4().hex
    credentials = {
        "email": f"user-{suffix}@example.com",
        "full_name": "Endpoint User",
        "password": "secure-password-123",
    }

    assert client.get("/api/users").status_code == 401
    assert client.post("/api/users", json=credentials).status_code == 401

    regular_user = client.post("/api/auth/register", json=credentials).json()
    regular_token = client.post(
        "/api/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    ).json()["access_token"]
    assert client.get("/api/users", headers=auth(regular_token)).status_code == 403
    assert client.post(
        "/api/users",
        headers=auth(regular_token),
        json={**credentials, "email": f"denied-{suffix}@example.com"},
    ).status_code == 403

    managed_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={**credentials, "email": f"managed-{suffix}@example.com"},
    )
    assert managed_user.status_code == 201
    user_id = managed_user.json()["id"]
    assert managed_user.json()["is_active"] is True
    assert client.post(
        "/api/users",
        headers=admin_headers,
        json={**credentials, "email": f"managed-{suffix}@example.com"},
    ).status_code == 409

    listed = client.get("/api/users?limit=1", headers=admin_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.get("/api/users?limit=101", headers=admin_headers).status_code == 422

    updated = client.patch(
        f"/api/users/{user_id}",
        headers=admin_headers,
        json={
            "email": f"updated-{suffix}@example.com",
            "full_name": "Updated Endpoint User",
            "password": "changed-password-123",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Endpoint User"
    assert client.post(
        "/api/auth/login",
        json={
            "email": f"updated-{suffix}@example.com",
            "password": "changed-password-123",
        },
    ).status_code == 200
    assert client.patch(
        f"/api/users/{user_id}", headers=admin_headers, json={"full_name": "x"}
    ).status_code == 422

    assert client.patch("/api/users/999999", headers=admin_headers, json={}).status_code == 404
    assert client.delete("/api/users/999999", headers=admin_headers).status_code == 404
    assert client.delete(
        f"/api/users/{user_id}", headers=admin_headers
    ).status_code == 204
    inactive_user = next(
        user for user in client.get("/api/users", headers=admin_headers).json()
        if user["id"] == user_id
    )
    assert inactive_user["is_active"] is False
    assert client.patch(
        f"/api/users/{user_id}", headers=admin_headers, json={"is_active": True}
    ).json()["is_active"] is True
    assert client.delete(
        f"/api/users/{user_id}", headers=admin_headers
    ).status_code == 204
    assert client.delete(
        f"/api/users/{user_id}", headers=admin_headers
    ).status_code == 204
    assert regular_user["is_active"] is True


def test_game_endpoints_cover_public_filters_admin_crud_and_errors(client, admin_token):
    admin_headers = auth(admin_token)
    suffix = uuid4().hex
    game_payload = new_game_payload(f"Endpoint Game {suffix}")

    assert client.post("/api/games", json=game_payload).status_code == 401

    customer_credentials = {
        "email": f"game-customer-{suffix}@example.com",
        "full_name": "Game Customer",
        "password": "secure-password-123",
    }
    client.post("/api/auth/register", json=customer_credentials)
    customer_token = client.post(
        "/api/auth/login",
        json={
            "email": customer_credentials["email"],
            "password": customer_credentials["password"],
        },
    ).json()["access_token"]
    assert client.post(
        "/api/games",
        headers=auth(customer_token),
        json=game_payload,
    ).status_code == 403

    created = client.post("/api/games", headers=admin_headers, json=game_payload)
    assert created.status_code == 201
    game_id = created.json()["id"]
    assert created.json()["title"] == game_payload["title"]

    listing = client.get("/api/games")
    assert listing.status_code == 200
    assert any(game["id"] == game_id for game in listing.json())
    assert client.get("/api/games?category=Aventura").json()
    assert any(
        game["id"] == game_id
        for game in client.get(f"/api/games?search={game_payload['title']}").json()
    )
    assert client.get(f"/api/games/{game_id}").json()["title"] == game_payload["title"]
    assert client.get("/api/games/999999").status_code == 404

    updated = client.patch(
        f"/api/games/{game_id}", headers=admin_headers, json={"price": "199.99"}
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == "199.99"
    assert client.patch(
        f"/api/games/{game_id}", headers=admin_headers, json={"price": "0"}
    ).status_code == 422
    assert client.patch("/api/games/999999", headers=admin_headers, json={}).status_code == 404
    assert client.delete(f"/api/games/{game_id}", headers=auth(customer_token)).status_code == 403
    assert client.delete(f"/api/games/{game_id}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/games/{game_id}").status_code == 404
    assert client.delete("/api/games/999999", headers=admin_headers).status_code == 404


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "T" * 121),
        ("description", "D" * 2001),
        ("platform", "P" * 41),
        ("category", "C" * 41),
        ("price", "100000000.00"),
        ("stock", 10001),
        ("image_url", "https://example.com/" + "x" * 500),
    ],
)
def test_game_creation_rejects_values_over_schema_limits(client, admin_token, field, value):
    response = client.post(
        "/api/games",
        headers=auth(admin_token),
        json={**new_game_payload(f"Boundary Game {uuid4().hex}"), field: value},
    )
    assert response.status_code == 422


def test_game_creation_accepts_unicode_punctuation_and_exact_field_limits(client, admin_token):
    payload = {
        "title": "¡Élite! O'Connor " + "T" * 103,
        "description": "Á" * 2000,
        "platform": "P" * 40,
        "category": "C" * 40,
        "price": "99999999.99",
        "image_url": "https://example.com/" + "x" * 480,
        "stock": 10000,
    }
    created = client.post("/api/games", headers=auth(admin_token), json=payload)
    assert created.status_code == 201
    assert created.json()["title"].startswith("¡Élite! O'Connor")
    assert created.json()["stock"] == 10000


def test_purchase_endpoints_cover_auth_validation_stock_and_persistence(client, admin_token):
    admin_headers = auth(admin_token)
    suffix = uuid4().hex
    game = client.post(
        "/api/games",
        headers=admin_headers,
        json=new_game_payload(f"Purchase Endpoint Game {suffix}"),
    ).json()
    credentials = {
        "email": f"buyer-{suffix}@example.com",
        "full_name": "Purchase Buyer",
        "password": "secure-password-123",
    }
    client.post("/api/auth/register", json=credentials)
    token = client.post(
        "/api/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    ).json()["access_token"]
    headers = auth(token)

    purchase_payload = {"items": [{"game_id": game["id"], "quantity": 2}]}
    assert client.get("/api/purchases").status_code == 401
    assert client.post("/api/purchases", json=purchase_payload).status_code == 401
    assert client.post(
        "/api/purchases", headers=headers, json={"items": []}
    ).status_code == 422
    assert client.post(
        "/api/purchases",
        headers=headers,
        json={"items": [{"game_id": game["id"], "quantity": 11}]},
    ).status_code == 422
    assert client.post(
        "/api/purchases",
        headers=headers,
        json={"items": [{"game_id": 999999, "quantity": 1}]},
    ).status_code == 404
    assert client.post(
        "/api/purchases",
        headers=headers,
        json={"items": [{"game_id": game["id"], "quantity": 6}]},
    ).status_code == 409

    purchase = client.post("/api/purchases", headers=headers, json=purchase_payload)
    assert purchase.status_code == 201
    assert purchase.json()["total"] == "500.00"
    history = client.get("/api/purchases", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == purchase.json()["id"]
    assert client.get(f"/api/games/{game['id']}").json()["stock"] == 3
    assert client.delete(
        f"/api/games/{game['id']}", headers=admin_headers
    ).status_code == 409

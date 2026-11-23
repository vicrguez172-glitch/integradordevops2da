import re
import uuid

from playwright.sync_api import Page, expect


def register_customer(page: Page, email: str) -> None:
    page.get_by_role("button", name="Entrar").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("button", name="Crea una").click()
    name = dialog.get_by_label("Nombre completo")
    assert name.get_attribute("maxlength") == "120"
    name.fill("José O'Connor-Smith")
    dialog.get_by_label("Correo electrónico").fill(email)
    password = dialog.locator("#register-password")
    password.fill("short")
    assert password.evaluate("(element) => element.validity.tooShort")
    dialog.get_by_role("button", name="Mostrar contraseña").click()
    expect(password).to_have_attribute("type", "text")
    dialog.get_by_role("button", name="Ocultar contraseña").click()
    expect(password).to_have_attribute("type", "password")
    expect(password).to_have_attribute("maxlength", "128")
    password.fill("Tést!Password-2026")
    dialog.get_by_role("button", name="Crear cuenta").click()
    expect(page.get_by_role("button", name="Abrir mi cuenta")).to_contain_text("José")
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()


def test_invalid_login_shows_error_modal(page: Page, app_url, api_request_metrics):
    page.goto(app_url)
    page.get_by_role("button", name="Entrar").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Correo electrónico").fill("missing-user@example.com")
    dialog.locator("#login-password").fill("incorrect-password")
    dialog.get_by_role("button", name="Iniciar sesión").click()

    error_dialog = page.get_by_role("dialog", name="No se pudo completar")
    expect(error_dialog).to_contain_text("Correo o contraseña incorrectos")
    error_dialog.get_by_role("button", name="Entendido").click()
    assert any(
        metric["endpoint"] == "/api/auth/login"
        and metric["method"] == "POST"
        and metric["status_code"] == 401
        and "timestamp" in metric
        and "response_time_ms" in metric
        for metric in api_request_metrics
    )


def test_header_footer_and_auth_buttons_navigate_correctly(page: Page, app_url):
    page.goto(app_url)
    page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
        "button", name="Crear cuenta"
    ).click()
    dialog = page.get_by_role("dialog", name="Crea tu cuenta")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Inicia sesión").click()
    expect(page.get_by_role("dialog", name="Bienvenido de vuelta")).to_be_visible()
    page.get_by_role("button", name="Cerrar").click()

    page.get_by_role("button", name="Abrir carrito").click()
    expect(page.get_by_role("heading", name="Tu carrito", exact=True)).to_be_visible()
    page.get_by_role("button", name="Ver catálogo").click()
    expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()
    page.get_by_role("button", name="Explorar catálogo").click()
    expect(page.locator("#catalogo")).to_be_in_viewport()

    page.get_by_role("navigation", name="Explorar tienda").get_by_role(
        "button", name="Carrito"
    ).click()
    expect(page.get_by_role("heading", name="Tu carrito", exact=True)).to_be_visible()
    page.get_by_role("navigation", name="Explorar tienda").get_by_role(
        "button", name="Inicio y catálogo"
    ).click()
    expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()


def test_cart_add_quantity_remove_and_checkout_guard(page: Page, app_url):
    page.goto(app_url)
    game_card = page.locator(".game-card").first
    title = game_card.locator("h3").inner_text()
    game_card.get_by_role("button", name=re.compile("Agregar .* al carrito")).click()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()

    page.get_by_role("button", name="Abrir carrito").click()
    line = page.locator(".cart-line").filter(has_text=title)
    expect(line.locator(".quantity-control span")).to_have_text("1")
    line.get_by_role("button", name=f"Agregar uno de {title}").click()
    expect(line.locator(".quantity-control span")).to_have_text("2")
    expect(page.locator(".cart-count")).to_have_text("2")
    line.get_by_role("button", name=f"Quitar uno de {title}").click()
    expect(line.locator(".quantity-control span")).to_have_text("1")

    page.get_by_role("button", name="Continuar con la compra").click()
    expect(page.get_by_role("dialog", name="No se pudo completar")).to_contain_text(
        "Inicia sesión para finalizar tu compra"
    )
    page.get_by_role("dialog", name="No se pudo completar").get_by_role(
        "button", name="Entendido"
    ).click()
    expect(page.get_by_role("dialog", name="Bienvenido de vuelta")).to_be_visible()
    page.get_by_role("button", name="Cerrar").click()

    line.get_by_role("button", name=f"Eliminar {title}").click()
    expect(page.get_by_role("heading", name="Tu carrito está esperando")).to_be_visible()


def test_customer_can_register_purchase_and_view_history(page: Page, app_url, api_request_metrics):
    email = f"Cliente+{uuid.uuid4().hex[:10]}@Example.COM"
    page.goto(app_url)

    expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()
    footer = page.get_by_role("contentinfo")
    expect(footer).to_contain_text("no se realizan cargos reales")
    expect(footer.get_by_role("button", name="Volver arriba")).to_be_visible()
    game_cards = page.locator(".game-card")
    assert game_cards.count() >= 4
    game_title = game_cards.first.locator("h3").inner_text()
    game_cards.first.get_by_role("button", name=re.compile("Agregar .* al carrito")).click()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()

    register_customer(page, email)
    page.get_by_role("button", name="Abrir carrito").click()
    expect(page.get_by_role("heading", name="Tu carrito")).to_be_visible()
    expect(page.get_by_text(game_title)).to_be_visible()
    page.get_by_role("button", name="Continuar con la compra").click()
    page.get_by_role("button", name="Confirmar pedido").click()

    expect(page.get_by_text(re.compile("Compra #\\d+ confirmada"))).to_be_visible()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()
    expect(page.get_by_text(game_title)).to_be_visible()
    assert any(
        metric["endpoint"] == "/api/purchases"
        and metric["method"] == "POST"
        and metric["status_code"] == 201
        and "timestamp" in metric
        and "response_time_ms" in metric
        for metric in api_request_metrics
    )


def test_admin_can_manage_users_and_game_catalog(
    page: Page, app_url, admin_credentials, api_request_metrics
):
    email, password = admin_credentials
    suffix = uuid.uuid4().hex[:8]
    new_user_name = f"Usuario José O'Connor {suffix}"
    new_user_email = f"Usuario+{suffix}@Example.COM"
    game_title = f"Juego ¡Élite! {suffix}"
    page.goto(app_url)

    page.get_by_role("button", name="Entrar").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Correo electrónico").fill(email)
    dialog.locator("#login-password").fill(password)
    dialog.get_by_role("button", name="Iniciar sesión").click()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()
    page.get_by_role("button", name="Administrar").click()
    expect(page.get_by_role("heading", name="Administración")).to_be_visible()

    create_name = page.get_by_label("Nombre completo", exact=True)
    assert create_name.get_attribute("maxlength") == "120"
    create_name.fill(new_user_name)
    page.get_by_label("Correo electrónico", exact=True).fill(new_user_email)
    create_password = page.get_by_label("Contraseña inicial")
    assert create_password.get_attribute("minlength") == "8"
    assert create_password.get_attribute("maxlength") == "128"
    create_password.fill("temporary-pass-2026")
    page.get_by_role("button", name="Mostrar contraseña").click()
    expect(create_password).to_have_attribute("type", "text")
    page.get_by_role("button", name="Ocultar contraseña").click()
    expect(create_password).to_have_attribute("type", "password")
    page.locator('select[name="userRole"]').select_option("admin")
    page.get_by_role("button", name="+ Crear usuario").click()
    user_row = page.get_by_role("row").filter(has_text=new_user_name)
    expect(user_row).to_be_visible()
    expect(user_row).to_contain_text(new_user_email.lower())
    expect(user_row.get_by_text("Admin")).to_be_visible()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()
    page.get_by_label("Buscar usuario").fill(new_user_name)
    page.locator('select[name="userRoleFilter"]').select_option("admin")
    page.locator('select[name="userStatusFilter"]').select_option("active")
    user_row.get_by_role("button", name="Editar").click()
    edit_form = page.locator(".user-edit-form")
    edit_name = page.get_by_label("Nombre del usuario")
    assert edit_name.get_attribute("maxlength") == "120"
    edit_name.fill(new_user_name + " editado")
    page.get_by_label("Correo del usuario").fill(f"editado-{suffix}@example.com")
    edit_password = page.get_by_label("Nueva contraseña")
    assert edit_password.get_attribute("minlength") == "8"
    assert edit_password.get_attribute("maxlength") == "128"
    edit_password.fill("changed-password-2026")
    edit_form.get_by_role("button", name="Mostrar contraseña").click()
    expect(edit_password).to_have_attribute("type", "text")
    edit_form.get_by_role("button", name="Ocultar contraseña").click()
    expect(edit_password).to_have_attribute("type", "password")
    page.get_by_role("button", name="Guardar cambios").click()
    expect(page.get_by_text(new_user_name + " editado")).to_be_visible()
    expect(page.get_by_text(f"editado-{suffix}@example.com")).to_be_visible()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()

    page.get_by_role("button", name="+ Agregar juego").click()
    page.get_by_label("Título").fill(game_title)
    assert page.get_by_label("Título").get_attribute("maxlength") == "120"
    page.locator('input[name="gamePlatform"]').fill("PC")
    page.locator('input[name="gameCategory"]').fill("Aventura")
    page.get_by_label("Precio (MXN)").fill("399")
    page.get_by_label("Existencias").fill("8")
    page.get_by_label("URL de portada").fill("https://example.com/portada.jpg")
    description = page.get_by_label("Descripción")
    assert description.get_attribute("maxlength") == "2000"
    description.fill("Juego de prueba automatizada para el catálogo.")
    page.get_by_role("button", name="Guardar juego").click()
    game_row = page.get_by_role("row").filter(has_text=game_title)
    expect(game_row).to_be_visible()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()
    page.get_by_label("Buscar juego en inventario").fill(game_title)
    page.locator('select[name="inventoryCategory"]').select_option("Aventura")
    page.locator('select[name="inventoryPlatform"]').select_option("PC")
    game_row.get_by_role("button", name="Editar").click()
    page.get_by_label("Precio (MXN)").fill("450")
    page.get_by_role("button", name="Guardar juego").click()
    expect(page.get_by_role("row").filter(has_text=game_title).get_by_text("$450.00")).to_be_visible()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()

    user_row = page.get_by_role("row").filter(has_text=new_user_name + " editado")
    user_row.get_by_role("button", name="Dar de baja").click()
    confirm_dialog = page.get_by_role("dialog", name="Confirmar eliminación")
    expect(confirm_dialog).to_contain_text(new_user_name + " editado")
    expect(confirm_dialog).to_contain_text("sus compras se conservarán")
    confirm_dialog.get_by_role("button", name="Dar de baja").click()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()
    page.locator('select[name="userStatusFilter"]').select_option("inactive")
    expect(user_row.get_by_text("Baja lógica")).to_be_visible()
    user_row.get_by_role("button", name="Reactivar").click()
    page.get_by_role("dialog", name="Listo").get_by_role("button", name="Entendido").click()
    page.locator('select[name="userStatusFilter"]').select_option("active")
    expect(user_row.get_by_text("Activo")).to_be_visible()
    page.get_by_role("row").filter(has_text=game_title).get_by_role("button", name="Eliminar").click()
    page.get_by_role("dialog", name="Confirmar eliminación").get_by_role(
        "button", name="Eliminar"
    ).click()
    expect(page.get_by_role("row").filter(has_text=game_title)).to_have_count(0)
    assert any(
        metric["endpoint"] == "/api/users"
        and metric["method"] == "POST"
        and metric["status_code"] == 201
        for metric in api_request_metrics
    )

import os
import re
from decimal import Decimal
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Browser, Page, expect


VIEWPORTS = (
    (360, 800),
    (390, 844),
    (768, 1024),
    (1024, 768),
    (1440, 900),
)

ANONYMOUS_NAV_ACTIONS = (
    "header_cart",
    "footer_cart",
    "footer_catalog",
    "header_login",
    "footer_login",
    "footer_register",
    "login_switch_register",
    "register_switch_login",
    "hero_catalog",
    "close_auth",
)
ADMIN_NAV_ACTIONS = (
    "footer_admin",
    "footer_account",
    "profile_account",
    "logout",
    "admin_users_tab",
    "admin_inventory_tab",
    "admin_back",
    "footer_catalog",
    "brand_home",
    "primary_nav",
)
NAVIGATION_CASES = tuple(
    (role, action, viewport)
    for role, actions in (
        ("anonymous", ANONYMOUS_NAV_ACTIONS),
        ("admin", ADMIN_NAV_ACTIONS),
    )
    for action in actions
    for viewport in range(len(VIEWPORTS))
)

CART_ACTION_SEQUENCES = (
    (),
    ("increment",),
    ("decrement",),
    ("increment", "increment"),
    ("increment", "decrement"),
    ("increment", "decrement", "decrement"),
    ("increment", "increment", "decrement"),
    ("increment", "increment", "decrement", "decrement"),
    ("increment", "decrement", "increment"),
    ("increment", "increment", "increment"),
    ("increment", "increment", "increment", "decrement"),
    ("increment", "increment", "decrement", "decrement", "decrement"),
    ("remove",),
    ("increment", "remove"),
    ("increment", "increment", "remove"),
)
CART_CASES = tuple(
    (game_index, actions, entry, viewport)
    for game_index in range(4)
    for actions in CART_ACTION_SEQUENCES
    for entry in ("quick_add", "card_button")
    for viewport in range(4)
)

AUTH_ENTRY_POINTS = (
    ("header_login", "login"),
    ("footer_login", "login"),
    ("footer_register", "register"),
    ("login_switch_register", "register"),
    ("register_switch_login", "login"),
)
AUTH_PROFILES = (
    ("Éx", "Player+Tag@Example.COM", "Pässword!9"),
    ("A", "player@example.com", "Password9!"),
    ("", "player@example.com", "Password9!"),
    ("N" * 120, "player@example.com", "P" * 128),
    ("María-José O'Connor", "Gamer+test@Example.COM", "Áventura!2026"),
    ("Test Player", "invalid-email", "Password9!"),
    ("Test Player", "", "Password9!"),
    ("Test Player", "player@example.com", "short7"),
    ("Test Player", "player@example.com", ""),
    ("Test Player", "player@example.com", "P" * 128),
    ("O'Neil-Smith", "player+one@example.com", "UpperLower!9"),
    ("Ángela & José", "UPPER.CASE@EXAMPLE.COM", "Secure!Pass2026"),
    ("Zoë 🎮", "player@example.com", "Pässw0rd!"),
    ("Test Player", "player name@example.com", "Password9!"),
    ("NIVEL Tester", "PLAYER+TAG@EXAMPLE.COM", "MIXED-case!42"),
    ("Usuario ¡Élite!", "player@example.com", "1234567!A"),
)
AUTH_CASES = tuple(
    (entry, profile_index, viewport)
    for entry in AUTH_ENTRY_POINTS
    for profile_index in range(len(AUTH_PROFILES))
    for viewport in range(4)
)

USER_NAMES = (
    "A",
    "Éx",
    "José O'Connor",
    "N" * 120,
    "Nombre-123",
)
USER_EMAILS = (
    "cliente@example.com",
    "User+Tag@Example.COM",
    "invalid-email",
    "",
    "duplicado@example.com",
)
CREATE_PASSWORDS = ("short7", "Pässw0rd!", "p" * 128)
EDIT_PASSWORDS = ("", "short7", "Pässw0rd!", "p" * 128)


def _email_is_valid(value: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) is not None


def _user_case(mode: str, name: str, email: str, password: str, role: str):
    password_valid = not password or len(password) >= 8
    return (
        mode,
        name,
        email,
        password,
        role,
        2 <= len(name) <= 120 and _email_is_valid(email) and password_valid,
    )


USER_CASES = tuple(
    [
        _user_case("create", name, email, password, role)
        for name in USER_NAMES
        for email in USER_EMAILS
        for password in CREATE_PASSWORDS
        for role in ("customer", "admin")
    ]
    + [
        _user_case("edit", name, email, password, role)
        for name in USER_NAMES
        for email in USER_EMAILS
        for password in EDIT_PASSWORDS
        for role in ("customer", "admin")
    ]
)


def _valid_game(**overrides: str) -> tuple[dict[str, str], bool]:
    values = {
        "title": "Sample Game",
        "description": "A game description long enough.",
        "platform": "PC",
        "category": "Aventura",
        "price": "10.00",
        "stock": "1",
        "image_url": "https://example.com/game.jpg",
    }
    values.update(overrides)
    valid = (
        2 <= len(values["title"]) <= 120
        and 10 <= len(values["description"]) <= 2000
        and 2 <= len(values["platform"]) <= 40
        and 2 <= len(values["category"]) <= 40
        and Decimal("0.01") <= Decimal(values["price"]) <= Decimal("99999999.99")
        and Decimal(values["price"]) * 100 % 1 == 0
        and Decimal("0") <= Decimal(values["stock"]) <= Decimal("10000")
        and Decimal(values["stock"]) % 1 == 0
        and urlsplit(values["image_url"]).scheme in {"http", "https"}
        and bool(urlsplit(values["image_url"]).netloc)
        and len(values["image_url"]) <= 500
    )
    return values, valid


def build_game_form_cases():
    cases = [
        _valid_game(title=""),
        _valid_game(title="A"),
        _valid_game(title="É!"),
        _valid_game(title="T" * 120),
        _valid_game(title="¡Élite! O'Connor"),
        _valid_game(description=""),
        _valid_game(description="D" * 9),
        _valid_game(description="Ácción: misión especial."),
        _valid_game(description="D" * 2000),
        _valid_game(platform=""),
        _valid_game(platform="P"),
        _valid_game(platform="PC"),
        _valid_game(platform="P" * 40),
        _valid_game(platform="Consola+"),
        _valid_game(category=""),
        _valid_game(category="A"),
        _valid_game(category="R!"),
        _valid_game(category="C" * 40),
        _valid_game(category="Acción & RPG"),
        _valid_game(price="0"),
        _valid_game(price="0.01"),
        _valid_game(price="99999999.99"),
        _valid_game(price="100000000"),
        _valid_game(price="1.001"),
        _valid_game(stock="-1"),
        _valid_game(stock="0"),
        _valid_game(stock="10000"),
        _valid_game(stock="10001"),
        _valid_game(stock="1.5"),
        _valid_game(image_url=""),
        _valid_game(image_url="not a URL"),
        _valid_game(image_url="https://example.com/cover.jpg?edition=deluxe&lang=es"),
        _valid_game(image_url="https://example.com/" + "p" * 480),
        _valid_game(image_url="https://example.com/path with spaces"),
        _valid_game(
            title="T" * 120,
            description="D" * 2000,
            platform="P" * 40,
            category="C" * 40,
            price="99999999.99",
            stock="10000",
            image_url="https://example.com/" + "p" * 480,
        ),
        _valid_game(
            title="¡Élite! O'Connor",
            description="Descripción: acción, misión y aventura especial.",
            platform="Nintendo Switch",
            category="Acción & RPG",
            price="0.01",
            stock="0",
            image_url="https://example.com/portada.jpg?edition=deluxe&lang=es",
        ),
        _valid_game(title="A", description="short"),
        _valid_game(price="0", stock="-1"),
        _valid_game(platform="", category=""),
        _valid_game(image_url="not a URL", title=""),
        _valid_game(stock="10000", price="0.01"),
        _valid_game(title="Élite 2026", description="Descripción válida con símbolos ¡y acentos!"),
        _valid_game(platform="P+" * 20, category="C+" * 20),
    ]
    return tuple(cases)


GAME_FORM_CASES = build_game_form_cases()
GAME_CASES = tuple(
    (case_index, mode, viewport)
    for case_index in range(len(GAME_FORM_CASES))
    for mode in ("create", "edit")
    for viewport in range(len(VIEWPORTS))
)

FILTER_CASES = tuple(
    (query, category)
    for query in ("", "HYRULE", "PC", "__no_catalog_match__")
    for category in ("Todos", "Aventura", "Carreras", "RPG", "Acción")
)

assert len(NAVIGATION_CASES) == 100
assert len(CART_CASES) == 480
assert len(AUTH_CASES) == 320
assert len(USER_CASES) == 350
assert len(GAME_CASES) == 430
assert len(FILTER_CASES) == 20
assert (
    len(NAVIGATION_CASES)
    + len(CART_CASES)
    + len(AUTH_CASES)
    + len(USER_CASES)
    + len(GAME_CASES)
    + len(FILTER_CASES)
    == 1700
)


def _login_as_admin(page: Page) -> None:
    page.get_by_role("button", name="Entrar").click()
    dialog = page.get_by_role("dialog", name="Bienvenido de vuelta")
    dialog.get_by_label("Correo electrónico").fill(
        os.getenv("E2E_ADMIN_EMAIL", "admin@example.com")
    )
    dialog.locator("#login-password").fill(
        os.getenv("E2E_ADMIN_PASSWORD", "local-admin-change-this")
    )
    dialog.get_by_role("button", name="Iniciar sesión").click()
    page.get_by_role("dialog", name="Listo").get_by_role(
        "button", name="Entendido"
    ).click()


def _open_admin_from_footer(page: Page) -> None:
    page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
        "button", name="Administración"
    ).click()
    expect(page.get_by_role("heading", name="Administración")).to_be_visible()


@pytest.fixture(scope="module")
def matrix_page(browser: Browser, app_url: str):
    context = browser.new_context()
    context.add_init_script("window.localStorage.clear();")
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module")
def cart_matrix_page(browser: Browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module")
def auth_matrix_page(browser: Browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module")
def admin_matrix_page(browser: Browser, app_url: str):
    context = browser.new_context()
    page = context.new_page()
    response = page.goto(app_url)
    assert response is not None and response.status == 200
    _login_as_admin(page)
    _open_admin_from_footer(page)
    yield page
    context.close()


def _run_anonymous_navigation(page: Page, action: str) -> None:
    if action == "header_cart":
        page.get_by_role("button", name="Abrir carrito").click()
        expect(page.get_by_role("heading", name="Tu carrito", exact=True)).to_be_visible()
    elif action == "footer_cart":
        page.get_by_role("navigation", name="Explorar tienda").get_by_role(
            "button", name="Carrito"
        ).click()
        expect(page.get_by_role("heading", name="Tu carrito", exact=True)).to_be_visible()
    elif action == "footer_catalog":
        page.get_by_role("navigation", name="Explorar tienda").get_by_role(
            "button", name="Inicio y catálogo"
        ).click()
        expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()
    elif action == "header_login":
        page.get_by_role("button", name="Entrar").click()
        expect(page.get_by_role("dialog", name="Bienvenido de vuelta")).to_be_visible()
    elif action == "footer_login":
        page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
            "button", name="Iniciar sesión"
        ).click()
        expect(page.get_by_role("dialog", name="Bienvenido de vuelta")).to_be_visible()
    elif action == "footer_register":
        page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
            "button", name="Crear cuenta"
        ).click()
        expect(page.get_by_role("dialog", name="Crea tu cuenta")).to_be_visible()
    elif action == "login_switch_register":
        page.get_by_role("button", name="Entrar").click()
        page.get_by_role("dialog", name="Bienvenido de vuelta").get_by_role(
            "button", name="Crea una"
        ).click()
        expect(page.get_by_role("dialog", name="Crea tu cuenta")).to_be_visible()
    elif action == "register_switch_login":
        page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
            "button", name="Crear cuenta"
        ).click()
        page.get_by_role("dialog", name="Crea tu cuenta").get_by_role(
            "button", name="Inicia sesión"
        ).click()
        expect(page.get_by_role("dialog", name="Bienvenido de vuelta")).to_be_visible()
    elif action == "hero_catalog":
        page.get_by_role("button", name="Explorar catálogo").click()
        expect(page.locator("#catalogo")).to_be_in_viewport()
    elif action == "close_auth":
        page.get_by_role("button", name="Entrar").click()
        page.get_by_role("button", name="Cerrar").click()
        expect(page.get_by_role("dialog")).to_have_count(0)
    else:
        raise AssertionError(f"Unknown anonymous navigation action: {action}")


def _run_admin_navigation(page: Page, action: str, viewport_width: int) -> None:
    if action == "footer_admin":
        _open_admin_from_footer(page)
    elif action == "footer_account":
        page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
            "button", name="Mis compras"
        ).click()
        expect(page.get_by_role("heading", name=re.compile("Hola,"))).to_be_visible()
    elif action == "profile_account":
        page.get_by_role("button", name="Abrir mi cuenta").click()
        expect(page.get_by_role("heading", name=re.compile("Hola,"))).to_be_visible()
    elif action == "logout":
        page.get_by_role("button", name="Cerrar sesión").click()
        expect(page.get_by_role("button", name="Entrar")).to_be_visible()
    elif action == "admin_users_tab":
        _open_admin_from_footer(page)
        page.locator(".admin-tabs button").nth(0).click()
        expect(page.locator("#usuarios")).to_be_in_viewport()
    elif action == "admin_inventory_tab":
        _open_admin_from_footer(page)
        page.locator(".admin-tabs button").nth(1).click()
        expect(page.locator("#inventario")).to_be_in_viewport()
    elif action == "admin_back":
        _open_admin_from_footer(page)
        page.get_by_role("button", name="← Volver a la tienda").click()
        expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()
    elif action == "footer_catalog":
        _open_admin_from_footer(page)
        page.get_by_role("navigation", name="Explorar tienda").get_by_role(
            "button", name="Inicio y catálogo"
        ).click()
        expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()
    elif action == "brand_home":
        _open_admin_from_footer(page)
        page.get_by_role("link", name="Nivel, inicio").click()
        expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()
    elif action == "primary_nav":
        nav = page.get_by_role("navigation", name="Navegación principal")
        if viewport_width < 992:
            expect(nav).to_be_hidden()
        else:
            nav.get_by_role("button", name="Administrar").click()
            expect(page.get_by_role("heading", name="Administración")).to_be_visible()
    else:
        raise AssertionError(f"Unknown admin navigation action: {action}")


@pytest.mark.parametrize(
    ("role", "action", "viewport_index"),
    NAVIGATION_CASES,
    ids=tuple(
        f"nav-{role}-{action}-vp{viewport_index}"
        for role, action, viewport_index in NAVIGATION_CASES
    ),
)
def test_navigation_buttons_reach_their_destination(
    matrix_page: Page, app_url: str, role: str, action: str, viewport_index: int
):
    page = matrix_page
    width, height = VIEWPORTS[viewport_index]
    page.set_viewport_size({"width": width, "height": height})
    page.goto(app_url)
    expect(page.get_by_role("heading", name=re.compile("Juega a tu"))).to_be_visible()

    if role == "admin":
        _login_as_admin(page)
        _run_admin_navigation(page, action, width)
    else:
        _run_anonymous_navigation(page, action)


@pytest.mark.parametrize(
    ("game_index", "actions", "entry", "viewport_index"),
    CART_CASES,
    ids=tuple(
        f"cart-game{game_index}-sequence{sequence_index}-{entry}-vp{viewport_index}"
        for sequence_index, (game_index, actions, entry, viewport_index) in enumerate(
            CART_CASES, start=1
        )
    ),
)
def test_cart_buttons_apply_item_actions_and_totals(
    cart_matrix_page: Page,
    app_url: str,
    game_index: int,
    actions: tuple[str, ...],
    entry: str,
    viewport_index: int,
):
    page = cart_matrix_page
    width, height = VIEWPORTS[viewport_index]
    page.set_viewport_size({"width": width, "height": height})
    if page.url == "about:blank":
        page.goto(app_url)
    else:
        remaining_lines = page.locator(".cart-line").count()
        while remaining_lines:
            line_to_clear = page.locator(".cart-line").first
            line_to_clear.get_by_role("button").last.click()
            remaining_lines -= 1
            expect(page.locator(".cart-line")).to_have_count(remaining_lines)
        page.get_by_role("link", name="Nivel, inicio").click()
    card = page.locator(".game-card").nth(game_index)
    expect(card).to_be_visible()
    title = card.locator("h3").inner_text()
    price_text = card.locator(".game-buy-row strong").inner_text()
    price = Decimal(re.sub(r"[^\d.]", "", price_text))

    if entry == "quick_add":
        card.locator(".quick-add").click()
    else:
        card.locator(".game-buy-row button").click()
    page.get_by_role("dialog", name="Listo").get_by_role(
        "button", name="Entendido"
    ).click()
    page.get_by_role("button", name="Abrir carrito").click()

    line = page.locator(".cart-line").filter(has_text=title)
    quantity = 1
    for action in actions:
        if action == "increment":
            line.get_by_role("button", name=f"Agregar uno de {title}").click()
            quantity += 1
        elif action == "decrement":
            line.get_by_role("button", name=f"Quitar uno de {title}").click()
            quantity -= 1
        else:
            line.get_by_role("button", name=f"Eliminar {title}").click()
            quantity = 0

    expect(page.locator(".cart-count")).to_have_text(str(quantity))
    if quantity:
        expect(line.locator(".quantity-control span")).to_have_text(str(quantity))
        expect(page.locator(".summary-row").first).to_contain_text(
            f"Productos ({quantity})"
        )
        expect(page.locator(".summary-total strong")).to_have_text(
            f"${price * quantity:,.2f}"
        )
    else:
        expect(page.get_by_role("heading", name="Tu carrito está esperando")).to_be_visible()


@pytest.mark.parametrize(
    ("entry", "profile_index", "viewport_index"),
    AUTH_CASES,
    ids=tuple(
        f"auth-{entry[0]}-profile{profile_index}-vp{viewport_index}"
        for entry, profile_index, viewport_index in AUTH_CASES
    ),
)
def test_login_registration_routes_and_form_boundaries(
    auth_matrix_page: Page,
    app_url: str,
    entry: tuple[str, str],
    profile_index: int,
    viewport_index: int,
):
    page = auth_matrix_page
    width, height = VIEWPORTS[viewport_index]
    page.set_viewport_size({"width": width, "height": height})
    if page.url == "about:blank":
        page.goto(app_url)

    entry_point, mode = entry
    if entry_point == "header_login":
        page.get_by_role("button", name="Entrar").click()
    elif entry_point == "footer_login":
        page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
            "button", name="Iniciar sesión"
        ).click()
    elif entry_point == "footer_register":
        page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
            "button", name="Crear cuenta"
        ).click()
    elif entry_point == "login_switch_register":
        page.get_by_role("button", name="Entrar").click()
        page.get_by_role("dialog", name="Bienvenido de vuelta").get_by_role(
            "button", name="Crea una"
        ).click()
    else:
        page.get_by_role("navigation", name="Cuenta y administración").get_by_role(
            "button", name="Crear cuenta"
        ).click()
        page.get_by_role("dialog", name="Crea tu cuenta").get_by_role(
            "button", name="Inicia sesión"
        ).click()

    dialog_name = "Crea tu cuenta" if mode == "register" else "Bienvenido de vuelta"
    dialog = page.get_by_role("dialog", name=dialog_name)
    expect(dialog).to_be_visible()
    name, email, password_value = AUTH_PROFILES[profile_index]
    email_input = dialog.get_by_label("Correo electrónico")
    password_input = dialog.locator(
        "#register-password" if mode == "register" else "#login-password"
    )
    email_input.fill(email)
    password_input.fill(password_value)

    if mode == "register":
        name_input = dialog.get_by_label("Nombre completo")
        name_input.fill(name)
        assert name_input.get_attribute("maxlength") == "120"
        assert password_input.get_attribute("minlength") == "8"
        assert password_input.get_attribute("maxlength") == "128"
        expected_validity = (
            2 <= len(name) <= 120
            and _email_is_valid(email)
            and 8 <= len(password_value) <= 128
        )
    else:
        expected_validity = _email_is_valid(email) and bool(password_value)

    form = dialog.locator("form")
    assert form.evaluate("(element) => element.checkValidity()") is expected_validity
    dialog.get_by_role("button", name="Mostrar contraseña").click()
    expect(password_input).to_have_attribute("type", "text")
    dialog.get_by_role("button", name="Ocultar contraseña").click()
    expect(password_input).to_have_attribute("type", "password")
    dialog.get_by_role("button", name="Cerrar").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


@pytest.mark.parametrize(
    ("mode", "name", "email", "password", "role", "expected_validity"),
    USER_CASES,
    ids=tuple(
        f"user-{mode}-{name_index}-{email_index}-{password_index}-{role}"
        for mode, name_index, email_index, password_index, role in (
            (case[0], n, e, p, case[4])
            for case in USER_CASES
            for n in (USER_NAMES.index(case[1]),)
            for e in (USER_EMAILS.index(case[2]),)
            for p in (
                (CREATE_PASSWORDS if case[0] == "create" else EDIT_PASSWORDS).index(case[3]),
            )
        )
    ),
)
def test_admin_user_forms_enforce_roles_and_validation(
    admin_matrix_page: Page,
    app_url: str,
    mode: str,
    name: str,
    email: str,
    password: str,
    role: str,
    expected_validity: bool,
):
    page = admin_matrix_page
    if page.locator(".user-edit-form").count():
        page.locator(".user-edit-form").get_by_role("button", name="Cancelar").click()

    if mode == "create":
        form = page.locator(".admin-create-form")
        form.locator('input[name="userName"]').fill(name)
        form.locator('input[name="userEmail"]').fill(email)
        password_input = form.locator("#user-password")
        password_input.fill(password)
        form.locator('select[name="userRole"]').select_option(role)
        assert form.locator('input[name="userName"]').get_attribute("maxlength") == "120"
        assert password_input.get_attribute("minlength") == "8"
        assert password_input.get_attribute("maxlength") == "128"
        assert form.evaluate("(element) => element.checkValidity()") is expected_validity
    else:
        admin_email = os.getenv("E2E_ADMIN_EMAIL", "admin@example.com").lower()
        admin_row = page.locator("#usuarios tbody tr").filter(has_text=admin_email)
        admin_row.get_by_role("button", name="Editar").click()
        form = page.locator(".user-edit-form")
        name_input = form.get_by_label("Nombre del usuario")
        email_input = form.get_by_label("Correo del usuario")
        password_input = form.get_by_label("Nueva contraseña")
        name_input.fill(name)
        email_input.fill(email)
        password_input.fill(password)
        form.get_by_label("Rol del usuario").select_option(role)
        assert name_input.get_attribute("maxlength") == "120"
        assert password_input.get_attribute("minlength") == "8"
        assert password_input.get_attribute("maxlength") == "128"
        assert form.evaluate("(element) => element.checkValidity()") is expected_validity
        form.get_by_role("button", name="Cancelar").click()
        expect(page.locator(".user-edit-form")).to_have_count(0)


@pytest.mark.parametrize(
    ("case_index", "mode", "viewport_index"),
    GAME_CASES,
    ids=tuple(
        f"game-{case_index}-{mode}-vp{viewport_index}"
        for case_index, mode, viewport_index in GAME_CASES
    ),
)
def test_admin_game_forms_validate_fields_and_cancel_correctly(
    admin_matrix_page: Page,
    case_index: int,
    mode: str,
    viewport_index: int,
):
    page = admin_matrix_page
    width, height = VIEWPORTS[viewport_index]
    page.set_viewport_size({"width": width, "height": height})

    if page.locator(".game-editor").count():
        page.locator(".game-editor").get_by_role("button", name="Cancelar").click()
    if mode == "create":
        page.get_by_role("button", name="+ Agregar juego").click()
    else:
        page.locator("#inventario tbody tr").first.get_by_role(
            "button", name="Editar"
        ).click()

    values, expected_validity = GAME_FORM_CASES[case_index]
    form = page.locator(".game-editor")
    input_names = {
        "title": "gameTitle",
        "description": "gameDescription",
        "platform": "gamePlatform",
        "category": "gameCategory",
        "price": "gamePrice",
        "stock": "gameStock",
        "image_url": "gameImage",
    }
    for field, value in values.items():
        form.locator(f'[name="{input_names[field]}"]').fill(value)

    assert form.locator('[name="gameTitle"]').get_attribute("maxlength") == "120"
    assert form.locator('[name="gamePlatform"]').get_attribute("maxlength") == "40"
    assert form.locator('[name="gameCategory"]').get_attribute("maxlength") == "40"
    assert form.locator('[name="gameImage"]').get_attribute("maxlength") == "500"
    assert form.locator('[name="gameDescription"]').get_attribute("maxlength") == "2000"
    assert form.locator('[name="gamePrice"]').get_attribute("max") == "99999999.99"
    assert form.locator('[name="gameStock"]').get_attribute("max") == "10000"
    assert form.evaluate("(element) => element.checkValidity()") is expected_validity

    form.get_by_role("button", name="Cancelar").click()
    expect(page.locator(".game-editor")).to_have_count(0)


@pytest.mark.parametrize(
    ("query", "category"),
    FILTER_CASES,
    ids=tuple(f"catalog-{category.lower()}-{index}" for index, (_, category) in enumerate(FILTER_CASES)),
)
def test_catalog_search_and_category_filter(
    matrix_page: Page, app_url: str, query: str, category: str
):
    page = matrix_page
    page.goto(app_url)
    games_response = page.request.get(f"{app_url}/api/games")
    assert games_response.status == 200
    games = games_response.json()
    expected_titles = [
        game["title"]
        for game in games
        if (category == "Todos" or game["category"] == category)
        and (
            not query.strip()
            or query.strip().lower()
            in " ".join(
                str(game[field])
                for field in ("title", "description", "platform", "category")
            ).lower()
        )
    ]

    page.get_by_role("textbox", name="Buscar juegos").fill(query)
    page.get_by_role("button", name=category, exact=True).click()
    visible_titles = page.locator(".game-card h3")
    if expected_titles:
        expect(visible_titles).to_have_text(expected_titles)
    else:
        expect(visible_titles).to_have_count(0)
        expect(page.get_by_text("No encontramos ese juego")).to_be_visible()

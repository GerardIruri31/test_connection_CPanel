import json
import os
import re
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()

CPANEL_HOST = os.getenv("CPANEL_HOST")
CPANEL_PORT = os.getenv("CPANEL_PORT", "2083")
CPANEL_USER = os.getenv("CPANEL_USER")
CPANEL_API_TOKEN = os.getenv("CPANEL_API_TOKEN")
CPANEL_DOMAIN = os.getenv("CPANEL_DOMAIN")


class CPanelError(Exception):
    pass


def validate_configuration() -> None:
    variables = {
        "CPANEL_HOST": CPANEL_HOST,
        "CPANEL_USER": CPANEL_USER,
        "CPANEL_API_TOKEN": CPANEL_API_TOKEN,
        "CPANEL_DOMAIN": CPANEL_DOMAIN,
    }

    missing = [name for name, value in variables.items() if not value]

    if missing:
        raise RuntimeError(
            f"Faltan variables en .env: {', '.join(missing)}"
        )


def hide_sensitive_params(params: dict[str, Any]) -> dict[str, Any]:
    """Oculta contraseñas antes de imprimir los parámetros."""
    safe_params = {}

    for key, value in params.items():
        if "password" in key.lower() or "token" in key.lower():
            safe_params[key] = "********"
        else:
            safe_params[key] = value

    return safe_params


def call_cpanel_uapi(
    module: str,
    function: str,
    params: dict[str, Any] | None = None,
) -> Any:
    validate_configuration()

    params = params or {}

    url = (
        f"https://{CPANEL_HOST}:{CPANEL_PORT}"
        f"/execute/{module}/{function}"
    )

    headers = {
        "Authorization": (
            f"cpanel {CPANEL_USER}:{CPANEL_API_TOKEN}"
        ),
        "Accept": "application/json",
    }

    print("\n========== DEPURACIÓN CPANEL ==========")
    print("URL:", url)
    print("Usuario cPanel:", CPANEL_USER)
    print("Parámetros:")
    print(json.dumps(
        hide_sensitive_params(params),
        indent=2,
        ensure_ascii=False,
    ))

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise CPanelError(
            f"Error de conexión con cPanel: {exc}"
        ) from exc

    print("\nHTTP status:", response.status_code)
    print(
        "Content-Type:",
        response.headers.get("Content-Type"),
    )
    print("\nRespuesta cruda:")
    print(response.text[:5000])

    try:
        payload = response.json()
    except ValueError as exc:
        raise CPanelError(
            "La respuesta no es JSON. Revisa la respuesta cruda."
        ) from exc

    print("\nRespuesta JSON:")
    print(json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    ))

    if response.status_code != 200:
        raise CPanelError(
            f"cPanel respondió con HTTP {response.status_code}"
        )

    result = payload.get("result")

    if not isinstance(result, dict):
        raise CPanelError(
            f"La respuesta no contiene result válido: {payload}"
        )

    if result.get("status") != 1:
        details = (
            result.get("errors")
            or result.get("messages")
            or result.get("warnings")
            or result.get("data")
            or payload
        )

        if isinstance(details, list):
            message = "; ".join(str(item) for item in details)
        elif isinstance(details, dict):
            message = json.dumps(
                details,
                ensure_ascii=False,
            )
        else:
            message = str(details)

        raise CPanelError(
            f"cPanel rechazó la operación: {message}"
        )

    return result.get("data")


def test_connection() -> None:
    """Comprueba primero que usuario y token funcionen."""
    print("\nProbando autenticación...")

    accounts = call_cpanel_uapi(
        module="Email",
        function="list_pops",
    )

    print("\nAUTENTICACIÓN CORRECTA")
    print("Cuentas encontradas:", len(accounts or []))


def create_email_account(
    username: str,
    password: str,
    quota_mb: int = 250,
) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", username):
        raise ValueError(
            "El usuario contiene caracteres no permitidos."
        )

    data = call_cpanel_uapi(
        module="Email",
        function="add_pop",
        params={
            "email": username,
            "password": password,
            "domain": CPANEL_DOMAIN,
            "quota": quota_mb,
            "send_welcome_email": 0,
        },
    )

    email = f"{username}@{CPANEL_DOMAIN}"

    print("\nCORREO CREADO CORRECTAMENTE")
    print("Correo:", email)
    print("Respuesta:", data)

    return email


if __name__ == "__main__":
    try:
        # Paso 1: prueba solamente la conexión.
        #test_connection()

        # Paso 2: descomenta después de que el paso 1 funcione.
        create_email_account(
             username="testGerard",
             password="Derard15042006",
             quota_mb=250,
        )

    except (
        ValueError,
        RuntimeError,
        CPanelError,
    ) as exc:
        print("\nERROR DETECTADO:")
        print(exc)
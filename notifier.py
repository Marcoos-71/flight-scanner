# ============================================================
#  notifier.py — Envío de avisos por email (Gmail)
# ============================================================
#  Usa SMTP de Gmail con una "contraseña de aplicación".
#  No requiere librerías externas (smtplib es estándar).
# ============================================================

import smtplib
from email.message import EmailMessage

import config


def send_email(subject, html_body, text_body=""):
    """Envía un email HTML a config.EMAIL_TO. Devuelve True si se envió.

    Si faltan credenciales, no falla: avisa por consola y devuelve False
    (útil para no romper el escaneo si el email no está configurado).
    """
    if not config.GMAIL_USER or not config.GMAIL_APP_PASSWORD:
        print("[notifier] Faltan GMAIL_USER / GMAIL_APP_PASSWORD; no se envía email.")
        print("[notifier] (El escaneo y la BD funcionan igual.)")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_USER
    msg["To"] = config.EMAIL_TO
    msg.set_content(text_body or "Abre este correo en un cliente que soporte HTML.")
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"[notifier] Email enviado a {config.EMAIL_TO}")
        return True
    except Exception as exc:  # noqa: BLE001  (queremos no romper el job)
        print(f"[notifier] Error enviando email: {exc}")
        return False


if __name__ == "__main__":
    ok = send_email(
        "🛫 Flight Scanner — prueba",
        "<h2>Funciona ✅</h2><p>Este es un email de prueba del Flight Scanner.</p>",
        "Funciona. Email de prueba del Flight Scanner.",
    )
    print("Resultado:", ok)

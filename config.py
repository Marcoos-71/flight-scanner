# ============================================================
#  config.py — Configuración central del Flight Scanner
# ============================================================
#  Aquí NO van contraseñas ni la API key (este fichero se sube
#  a GitHub). Los secretos se leen de variables de entorno:
#    - en tu PC, desde secrets_local.py (no se sube a GitHub)
#    - en GitHub Actions, desde los "Secrets" del repositorio
# ============================================================

import os

# Carga los secretos locales si existen (no se sube a GitHub).
try:
    import secrets_local  # noqa: F401  -> rellena os.environ
except ModuleNotFoundError:
    pass


# --- Secretos (desde el entorno) ---
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

# --- Email (Gmail) para los avisos ---
GMAIL_USER = os.getenv("GMAIL_USER", "")              # tu_correo@gmail.com
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # contraseña de aplicación
EMAIL_TO = os.getenv("EMAIL_TO", GMAIL_USER)          # a quién enviar (por defecto, a ti)

# --- Base de datos ---
DB_PATH = "flights.db"

# --- Origen de todos los vuelos ---
ORIGIN = "MAD"

# --- Destinos a vigilar ---
# Formato: (IATA_destino, etiqueta_legible, umbral_aviso_eur)
# El umbral es el precio (ida) por debajo del cual se considera "chollo".
# Ajusta los umbrales a tu gusto: si pones un número alto, recibirás más avisos.
WATCHLIST = [
    ("HAN", "Madrid → Hanói (Vietnam)",        300),
    ("SGN", "Madrid → Ho Chi Minh (Vietnam)",  300),
    ("VTE", "Madrid → Vientián (Laos)",        450),
    ("FRU", "Madrid → Bishkek (Kirguistán)",   250),
    ("TBS", "Madrid → Tiflis (Georgia)",       150),
    ("EVN", "Madrid → Ereván (Armenia)",       200),
    ("SJJ", "Madrid → Sarajevo (Bosnia)",      100),
    ("BEG", "Madrid → Belgrado (Serbia)",       90),
]

# --- Fechas a consultar por destino ---
# Días en el futuro desde hoy. 3 fechas reparten el presupuesto y captan
# variaciones de precio a 1, 2 y 3 meses vista.
SCAN_DATES_AHEAD = [30, 60, 90]

# --- Scheduler local (solo para scheduler.py, opcional) ---
SCAN_INTERVAL_HOURS = 6

# --- Parámetros de búsqueda por defecto ---
DEFAULT_CURRENCY = "EUR"
DEFAULT_LANGUAGE = "es"
DEFAULT_ADULTS = 1


# ============================================================
#  Derivados para el dashboard (no editar normalmente)
# ============================================================
# El dashboard usa ROUTES, PRICE_ALERTS y REGIONS; los generamos
# a partir de WATCHLIST para tener una sola fuente de verdad.

ROUTES = [(ORIGIN, iata, label) for iata, label, _ in WATCHLIST]
PRICE_ALERTS = {label: threshold for _, label, threshold in WATCHLIST}

# --- Regiones para búsqueda por área (dashboard) ---
REGIONS = {
    "Europa del Este": ["WAW", "PRG", "BUD", "SOF", "KRK", "VNO"],
    "Europa del Norte": ["CPH", "ARN", "HEL", "OSL", "RIX", "TLL"],
    "Europa del Sur": ["ATH", "SKG", "DBV", "LIS", "FCO", "NAP"],
    "Cáucaso y Asia Central": ["TBS", "EVN", "FRU", "TAS", "ALA", "GYD"],
    "Balcanes": ["SJJ", "BEG", "TIA", "SKP", "TGD", "PRN"],
}

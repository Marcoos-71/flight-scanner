# ============================================================
#  database.py — Historial de precios en SQLite
# ============================================================
#  Guarda cada vuelo encontrado con un timestamp para poder
#  ver la evolución del precio en el tiempo.
# ============================================================

import sqlite3
from datetime import datetime, timedelta

import pandas as pd

import config


def _connect():
    """Abre una conexión a la base de datos SQLite."""
    return sqlite3.connect(config.DB_PATH)


def init_db():
    """Crea la base de datos y la tabla `flights` si no existen."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flights (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                origin      TEXT    NOT NULL,
                destination TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                price       REAL    NOT NULL,
                airline     TEXT,
                duration    TEXT,
                stops       INTEGER,
                departure   TEXT,
                arrival     TEXT,
                scanned_at  TEXT    NOT NULL
            )
            """
        )
        # Índice para acelerar las consultas de historial por ruta.
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_flights_route
            ON flights (origin, destination, scanned_at)
            """
        )


def save_flights(flights):
    """Inserta una lista de vuelos (dicts de api.py) con timestamp.

    Cada vuelo debe tener las claves: price, airline, duration, stops,
    departure, arrival, origin, destination, date. Devuelve el número
    de filas insertadas.
    """
    if not flights:
        return 0

    scanned_at = datetime.now().isoformat(timespec="seconds")

    rows = [
        (
            f["origin"],
            f["destination"],
            f["date"],
            f["price"],
            f.get("airline"),
            f.get("duration"),
            f.get("stops"),
            f.get("departure"),
            f.get("arrival"),
            scanned_at,
        )
        for f in flights
    ]

    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO flights (
                origin, destination, date, price, airline,
                duration, stops, departure, arrival, scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def get_history(origin, destination, days=30):
    """Historial de precios de una ruta en los últimos `days` días.

    Devuelve un DataFrame con todas las columnas de la tabla, ordenado
    por fecha de escaneo ascendente. DataFrame vacío si no hay datos.
    """
    since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")

    with _connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT * FROM flights
            WHERE origin = ? AND destination = ? AND scanned_at >= ?
            ORDER BY scanned_at ASC
            """,
            conn,
            params=(origin, destination, since),
        )
    return df


def get_cheapest_ever(origin, destination):
    """Devuelve el vuelo más barato registrado para una ruta.

    Devuelve un dict con las columnas de la fila, o None si no hay datos.
    """
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM flights
            WHERE origin = ? AND destination = ?
            ORDER BY price ASC
            LIMIT 1
            """,
            (origin, destination),
        ).fetchone()

    return dict(row) if row else None


# --- Prueba manual rápida ---
if __name__ == "__main__":
    init_db()
    print(f"Base de datos lista en {config.DB_PATH}")

    # Inserta un vuelo de ejemplo y lo recupera.
    ejemplo = [
        {
            "origin": "MAD",
            "destination": "BCN",
            "date": "2026-07-15",
            "price": 34.0,
            "airline": "Vueling",
            "duration": "1h 25m",
            "stops": 0,
            "departure": "07:30",
            "arrival": "08:55",
        }
    ]
    n = save_flights(ejemplo)
    print(f"Insertados {n} vuelo(s) de ejemplo")

    print("Más barato MAD→BCN:", get_cheapest_ever("MAD", "BCN"))
    print("Filas de historial:", len(get_history("MAD", "BCN")))

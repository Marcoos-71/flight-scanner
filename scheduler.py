# ============================================================
#  scheduler.py — Escaneo automático de precios
# ============================================================
#  Lanza búsquedas de todas las rutas de config.ROUTES cada
#  SCAN_INTERVAL_HOURS horas y guarda los resultados en la BD.
# ============================================================

from datetime import date, timedelta

import schedule
import time

import api
import config
import database


# Fecha por defecto a consultar en cada escaneo: dentro de 30 días.
# (SerpApi necesita una fecha concreta; usamos una futura razonable.)
def _default_date():
    return (date.today() + timedelta(days=30)).isoformat()


def run_scan(scan_date=None):
    """Busca todas las rutas de config.ROUTES y las guarda en la BD.

    `scan_date` es la fecha de vuelo a consultar ('YYYY-MM-DD'); si no
    se indica, se usa la de dentro de 30 días. Devuelve el total de
    vuelos guardados.
    """
    scan_date = scan_date or _default_date()
    total_saved = 0

    print(f"\n[scheduler] Escaneo iniciado para la fecha {scan_date}")
    for origin, destination, label in config.ROUTES:
        flights = api.search_flight(origin, destination, scan_date)
        saved = database.save_flights(flights)
        total_saved += saved

        cheapest = api.get_cheapest(flights)
        if cheapest:
            print(f"[scheduler] {label}: {len(flights)} vuelos, "
                  f"más barato {cheapest['price']}€ ({saved} guardados)")
        else:
            print(f"[scheduler] {label}: sin resultados")

    print(f"[scheduler] Escaneo terminado. Total guardado: {total_saved}\n")
    return total_saved


def start_scheduler():
    """Ejecuta run_scan() ahora y luego cada SCAN_INTERVAL_HOURS horas."""
    database.init_db()

    interval = config.SCAN_INTERVAL_HOURS
    print(f"[scheduler] Arrancando. Escaneo cada {interval}h. "
          f"Ctrl+C para detener.")

    # Primer escaneo inmediato para no esperar al primer intervalo.
    run_scan()

    schedule.every(interval).hours.do(run_scan)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # comprueba cada minuto si toca escanear
    except KeyboardInterrupt:
        print("\n[scheduler] Detenido por el usuario.")


if __name__ == "__main__":
    start_scheduler()

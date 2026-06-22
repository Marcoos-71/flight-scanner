# ============================================================
#  api.py — Llamadas a SerpApi (Google Flights)
# ============================================================
#  Consulta precios de vuelos vía Google Flights y normaliza
#  la respuesta de SerpApi al formato que usa el resto del
#  proyecto (database.py, scheduler.py, dashboard.py).
# ============================================================

import urllib.parse

import requests

import config

SERPAPI_ENDPOINT = "https://serpapi.com/search"


def booking_link(origin, destination, date, return_date=None):
    """Enlace a Google Flights con la ruta y fechas ya rellenadas.

    Si hay return_date, genera un enlace de ida y vuelta; si no, de ida.
    No consume búsquedas de SerpApi: es solo una URL para reservar.
    """
    if return_date:
        query = f"flights from {origin} to {destination} on {date} returning {return_date}"
    else:
        query = f"flights from {origin} to {destination} on {date} oneway"
    return "https://www.google.com/travel/flights?q=" + urllib.parse.quote(query)


def _format_duration(minutes):
    """Convierte una duración en minutos (int) a texto '1h 25m'."""
    if minutes is None:
        return ""
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return ""
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _time_only(datetime_str):
    """Extrae 'HH:MM' de un valor 'YYYY-MM-DD HH:MM' de SerpApi."""
    if not datetime_str:
        return ""
    parts = datetime_str.split(" ")
    return parts[1] if len(parts) > 1 else datetime_str


def _parse_flight(item, origin, destination, date, return_date=None):
    """Transforma un elemento de best_flights/other_flights en nuestro dict.

    En ida y vuelta, `price` es el total del viaje y los datos de tramo
    (duración, horas, escalas) corresponden al vuelo de IDA.
    """
    segments = item.get("flights", [])
    if not segments:
        return None

    first = segments[0]
    last = segments[-1]

    # La aerolínea principal: la del primer tramo (suele ser la operadora).
    airline = first.get("airline", "")

    # Número de escalas = tramos - 1.
    stops = len(segments) - 1

    return {
        "price": item.get("price"),
        "airline": airline,
        "duration": _format_duration(item.get("total_duration")),
        "duration_minutes": item.get("total_duration"),
        "stops": stops,
        "departure": _time_only(first.get("departure_airport", {}).get("time")),
        "arrival": _time_only(last.get("arrival_airport", {}).get("time")),
        "origin": origin,
        "destination": destination,
        "date": date,
        "return_date": return_date,
    }


def _filter_reasonable(results):
    """Descarta vuelos cuya duración supere DURATION_TOLERANCE × el más rápido.

    Si el filtro dejara la lista vacía (o no hay config), no filtra nada.
    """
    tol = getattr(config, "DURATION_TOLERANCE", None)
    durations = [f["duration_minutes"] for f in results if f.get("duration_minutes")]
    if not tol or not durations:
        return results

    limit = min(durations) * tol
    kept = [f for f in results
            if not f.get("duration_minutes") or f["duration_minutes"] <= limit]
    return kept or results


def search_flight(origin, destination, date, adults=config.DEFAULT_ADULTS,
                  return_date=None):
    """Consulta vuelos de `origin` a `destination` en `date`.

    Si se pasa `return_date`, busca ida y vuelta (el precio es el total
    del viaje); si no, solo ida. Aplica los filtros de escalas y duración
    de config. Devuelve una lista de dicts ordenada por precio (vacía si
    no hay resultados o error).
    """
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": date,
        "currency": config.DEFAULT_CURRENCY,
        "hl": config.DEFAULT_LANGUAGE,
        "adults": adults,
        "api_key": config.SERPAPI_KEY,
    }

    if return_date:
        params["type"] = "1"          # 1 = ida y vuelta
        params["return_date"] = return_date
    else:
        params["type"] = "2"          # 2 = solo ida

    # Filtro de escalas en origen (SerpApi: 0=cualquiera, 1=directo,
    # 2=≤1 escala, 3=≤2 escalas) -> MAX_STOPS + 1.
    max_stops = getattr(config, "MAX_STOPS", None)
    if max_stops is not None:
        params["stops"] = str(max_stops + 1)

    try:
        response = requests.get(SERPAPI_ENDPOINT, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"[api] Error consultando {origin}→{destination} ({date}): {exc}")
        return []

    if "error" in data:
        print(f"[api] SerpApi error {origin}→{destination}: {data['error']}")
        return []

    raw_flights = data.get("best_flights", []) + data.get("other_flights", [])

    results = []
    for item in raw_flights:
        flight = _parse_flight(item, origin, destination, date, return_date)
        if flight and flight["price"] is not None:
            results.append(flight)

    results = _filter_reasonable(results)
    results.sort(key=lambda f: f["price"])
    return results


def search_region(origin, region_name, date):
    """Busca vuelos desde `origin` a todos los destinos de una región.

    `region_name` debe existir en config.REGIONS. Devuelve todos los
    resultados de todos los destinos, ordenados por precio ascendente.
    """
    destinations = config.REGIONS.get(region_name)
    if destinations is None:
        print(f"[api] Región desconocida: {region_name!r}")
        return []

    all_results = []
    for destination in destinations:
        if destination == origin:
            continue
        all_results.extend(search_flight(origin, destination, date))

    all_results.sort(key=lambda f: f["price"])
    return all_results


def get_cheapest(results, nonstop=False):
    """Devuelve el vuelo más barato de una lista de resultados.

    Si `nonstop=True`, solo considera vuelos directos (sin escalas).
    Devuelve None si no hay ningún vuelo que cumpla el criterio.
    """
    candidates = results
    if nonstop:
        candidates = [f for f in results if f["stops"] == 0]
    if not candidates:
        return None
    return min(candidates, key=lambda f: f["price"])


def summarize(results):
    """Resume una lista de resultados para el dashboard.

    Devuelve un dict con:
      - "cheapest":          el vuelo más barato (puede tener escalas)
      - "cheapest_nonstop":  el vuelo directo más barato (None si no hay)
      - "all":               la lista completa, ordenada por precio
    """
    return {
        "cheapest": get_cheapest(results),
        "cheapest_nonstop": get_cheapest(results, nonstop=True),
        "all": sorted(results, key=lambda f: f["price"]),
    }


# --- Prueba manual rápida ---
if __name__ == "__main__":
    import json

    flights = search_flight("MAD", "BCN", "2026-07-15")
    print(f"Encontrados {len(flights)} vuelos MAD→BCN\n")

    resumen = summarize(flights)

    if resumen["cheapest"]:
        print("Más barato (con o sin escalas):")
        print(json.dumps(resumen["cheapest"], indent=2, ensure_ascii=False))

    if resumen["cheapest_nonstop"]:
        print("\nMás barato sin escalas:")
        print(json.dumps(resumen["cheapest_nonstop"], indent=2, ensure_ascii=False))
    else:
        print("\nNo hay vuelos directos disponibles.")

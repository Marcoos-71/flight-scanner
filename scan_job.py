# ============================================================
#  scan_job.py — Escaneo único + aviso por email
# ============================================================
#  Pensado para ejecutarse por cron (GitHub Actions) 2 veces
#  por semana. Escanea todos los destinos de config.WATCHLIST
#  en varias fechas, guarda en la BD y envía un email-resumen
#  destacando los "chollos" por debajo de su umbral.
#
#  Ejecutar a mano:  python scan_job.py
# ============================================================

import os
from datetime import date, datetime, timedelta

import api
import config
import database
import notifier

# Carpeta que publica GitHub Pages.
PAGE_PATH = os.path.join("docs", "index.html")


def _date_pairs():
    """Pares (ida, vuelta) 'YYYY-MM-DD' a consultar.

    La vuelta = ida + TRIP_LENGTH_DAYS (ida y vuelta).
    """
    today = date.today()
    pairs = []
    for d in config.SCAN_DATES_AHEAD:
        out = today + timedelta(days=d)
        back = out + timedelta(days=config.TRIP_LENGTH_DAYS)
        pairs.append((out.isoformat(), back.isoformat()))
    return pairs


def scan_all():
    """Escanea toda la watchlist. Devuelve (resumen, chollos).

    resumen: lista de dicts con el vuelo más barato encontrado por destino.
    chollos: subconjunto de resumen cuyo precio <= umbral del destino.
    """
    database.init_db()
    pairs = _date_pairs()

    n_searches = len(config.WATCHLIST) * len(pairs)
    print(f"[scan_job] {len(config.WATCHLIST)} destinos × {len(pairs)} fechas "
          f"(ida y vuelta, {config.TRIP_LENGTH_DAYS} días) "
          f"= {n_searches} búsquedas en esta ejecución.")

    resumen = []
    chollos = []

    for iata, label, threshold in config.WATCHLIST:
        best = None
        for out_date, return_date in pairs:
            flights = api.search_flight(config.ORIGIN, iata, out_date,
                                        return_date=return_date)
            database.save_flights(flights)
            cheapest = api.get_cheapest(flights)
            if cheapest and (best is None or cheapest["price"] < best["price"]):
                best = cheapest

        if not best:
            print(f"[scan_job] {label}: sin resultados")
            resumen.append({"label": label, "threshold": threshold, "flight": None})
            continue

        is_deal = best["price"] <= threshold
        print(f"[scan_job] {label}: mejor {best['price']:.0f}€ "
              f"(umbral {threshold}€){'  ⭐ CHOLLO' if is_deal else ''}")

        row = {"label": label, "threshold": threshold,
               "flight": best, "is_deal": is_deal}
        resumen.append(row)
        if is_deal:
            chollos.append(row)

    return resumen, chollos


# ============================================================
#  Construcción del email
# ============================================================

def _flight_cells(f):
    """Celdas HTML con los datos de un vuelo + enlace de compra."""
    stops = "directo" if f["stops"] == 0 else f"{f['stops']} escala(s)"
    link = api.booking_link(f["origin"], f["destination"], f["date"],
                            f.get("return_date"))
    fechas = f["date"]
    if f.get("return_date"):
        fechas = f"{f['date']} → {f['return_date']}"
    return (f"<td><b>{f['price']:.0f}€</b></td>"
            f"<td>{fechas}</td>"
            f"<td>{f['airline']}</td>"
            f"<td>{f['duration']}</td>"
            f"<td>{stops}</td>"
            f"<td><a href='{link}'>Comprar&nbsp;✈</a></td>")


def _table_html(resumen):
    """Tabla HTML completa (cabecera + filas) compartida por email y página."""
    rows = []
    for r in sorted(resumen, key=lambda x: (x["flight"] is None,
                                            x["flight"]["price"] if x["flight"] else 0)):
        if not r["flight"]:
            rows.append(f"<tr><td>{r['label']}</td>"
                        f"<td colspan='6' style='color:#888'>sin resultados</td></tr>")
            continue
        bg = "background:#eafbea;" if r.get("is_deal") else ""
        star = " ⭐" if r.get("is_deal") else ""
        rows.append(f"<tr style='{bg}'><td>{r['label']}{star}</td>"
                    f"{_flight_cells(r['flight'])}</tr>")

    return f"""\
<table cellpadding="6" cellspacing="0" border="0"
       style="border-collapse:collapse;font-size:14px">
  <tr style="background:#1a3a5c;color:#fff;text-align:left">
    <th>Destino</th><th>Precio i/v</th><th>Fechas (ida → vuelta)</th>
    <th>Aerolínea</th><th>Duración ida</th><th>Escalas</th><th>Reservar</th>
  </tr>
  {''.join(rows)}
</table>"""


def _deals_html(chollos):
    """Bloque de 'chollos' (vacío si no hay)."""
    if not chollos:
        return ""
    lines = "".join(
        f"<li><b>{r['label']}</b>: {r['flight']['price']:.0f}€ i/v "
        f"({r['flight']['date']} → {r['flight'].get('return_date', '?')}, "
        f"umbral {r['threshold']}€) — "
        f"<a href='{api.booking_link(r['flight']['origin'], r['flight']['destination'], r['flight']['date'], r['flight'].get('return_date'))}'>"
        f"comprar ✈</a></li>"
        for r in chollos
    )
    return (f"<h3 style='color:#1a7a1a'>⭐ Chollos por debajo de tu umbral</h3>"
            f"<ul>{lines}</ul>")


def build_email(resumen, chollos):
    """Devuelve (asunto, html) del email-resumen."""
    today = date.today().isoformat()

    if chollos:
        subject = f"🛫 {len(chollos)} chollo(s) de vuelos — {today}"
    else:
        subject = f"🛫 Resumen de vuelos (sin chollos) — {today}"

    html = f"""\
<html><body style="font-family:system-ui,sans-serif;color:#222">
  <h2>🛫 Flight Scanner — {today}</h2>
  {_deals_html(chollos)}
  <h3>Ida y vuelta más barata por destino (viaje de {config.TRIP_LENGTH_DAYS}
      días, próximos ~5 meses)</h3>
  {_table_html(resumen)}
  <p style="color:#888;font-size:12px;margin-top:16px">
    Precios de ida y vuelta orientativos vía Google Flights / SerpApi.
    Los umbrales y opciones se ajustan en config.py.
  </p>
</body></html>"""

    return subject, html


def build_page(resumen, chollos):
    """Página HTML autónoma para GitHub Pages (la que anclas en Firefox)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n_deals = len(chollos)
    badge = (f"<span style='background:#1a7a1a;color:#fff;padding:2px 8px;"
             f"border-radius:10px'>{n_deals} chollo(s)</span>"
             if n_deals else
             "<span style='background:#888;color:#fff;padding:2px 8px;"
             "border-radius:10px'>sin chollos ahora</span>")

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🛫 Flight Scanner</title>
</head>
<body style="font-family:system-ui,sans-serif;color:#222;max-width:900px;
             margin:0 auto;padding:16px">
  <h1 style="background:#1a3a5c;color:#fff;padding:16px;border-radius:8px">
    🛫 Flight Scanner
  </h1>
  <p>Última actualización: <b>{now}</b> &nbsp; {badge}</p>
  {_deals_html(chollos)}
  <h3>Ida y vuelta más barata por destino (viaje de {config.TRIP_LENGTH_DAYS}
      días, próximos ~5 meses)</h3>
  {_table_html(resumen)}
  <p style="color:#888;font-size:12px;margin-top:16px">
    Se actualiza automáticamente lunes y jueves. Precios de ida y vuelta
    orientativos vía Google Flights / SerpApi.
  </p>
</body></html>"""


def write_page(resumen, chollos):
    """Genera docs/index.html para GitHub Pages."""
    os.makedirs(os.path.dirname(PAGE_PATH), exist_ok=True)
    with open(PAGE_PATH, "w", encoding="utf-8") as fh:
        fh.write(build_page(resumen, chollos))
    print(f"[scan_job] Página generada en {PAGE_PATH}")


def main():
    resumen, chollos = scan_all()

    # 1) Página web (GitHub Pages)
    write_page(resumen, chollos)

    # 2) Email
    subject, html = build_email(resumen, chollos)
    notifier.send_email(subject, html)


if __name__ == "__main__":
    main()

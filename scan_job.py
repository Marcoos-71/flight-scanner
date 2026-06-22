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

from datetime import date, timedelta

import api
import config
import database
import notifier


def _dates_to_scan():
    """Lista de fechas 'YYYY-MM-DD' a consultar (de SCAN_DATES_AHEAD)."""
    today = date.today()
    return [(today + timedelta(days=d)).isoformat() for d in config.SCAN_DATES_AHEAD]


def scan_all():
    """Escanea toda la watchlist. Devuelve (resumen, chollos).

    resumen: lista de dicts con el vuelo más barato encontrado por destino.
    chollos: subconjunto de resumen cuyo precio <= umbral del destino.
    """
    database.init_db()
    dates = _dates_to_scan()

    n_searches = len(config.WATCHLIST) * len(dates)
    print(f"[scan_job] {len(config.WATCHLIST)} destinos × {len(dates)} fechas "
          f"= {n_searches} búsquedas en esta ejecución.")

    resumen = []
    chollos = []

    for iata, label, threshold in config.WATCHLIST:
        best = None
        for d in dates:
            flights = api.search_flight(config.ORIGIN, iata, d)
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
    """Celdas HTML con los datos de un vuelo."""
    stops = "directo" if f["stops"] == 0 else f"{f['stops']} escala(s)"
    return (f"<td><b>{f['price']:.0f}€</b></td>"
            f"<td>{f['date']}</td>"
            f"<td>{f['airline']}</td>"
            f"<td>{f['duration']}</td>"
            f"<td>{stops}</td>")


def build_email(resumen, chollos):
    """Devuelve (asunto, html) del email-resumen."""
    today = date.today().isoformat()

    if chollos:
        subject = f"🛫 {len(chollos)} chollo(s) de vuelos — {today}"
    else:
        subject = f"🛫 Resumen de vuelos (sin chollos) — {today}"

    rows = []
    for r in sorted(resumen, key=lambda x: (x["flight"] is None,
                                            x["flight"]["price"] if x["flight"] else 0)):
        if not r["flight"]:
            rows.append(f"<tr><td>{r['label']}</td>"
                        f"<td colspan='5' style='color:#888'>sin resultados</td></tr>")
            continue
        bg = "background:#eafbea;" if r.get("is_deal") else ""
        star = " ⭐" if r.get("is_deal") else ""
        rows.append(f"<tr style='{bg}'><td>{r['label']}{star}</td>"
                    f"{_flight_cells(r['flight'])}</tr>")

    deals_html = ""
    if chollos:
        deals_lines = "".join(
            f"<li><b>{r['label']}</b>: {r['flight']['price']:.0f}€ "
            f"el {r['flight']['date']} (umbral {r['threshold']}€)</li>"
            for r in chollos
        )
        deals_html = (f"<h3 style='color:#1a7a1a'>⭐ Chollos por debajo de tu umbral</h3>"
                      f"<ul>{deals_lines}</ul>")

    html = f"""\
<html><body style="font-family:system-ui,sans-serif;color:#222">
  <h2>🛫 Flight Scanner — {today}</h2>
  {deals_html}
  <h3>Precio más barato por destino (ida, próximos 3 meses)</h3>
  <table cellpadding="6" cellspacing="0" border="0"
         style="border-collapse:collapse;font-size:14px">
    <tr style="background:#1a3a5c;color:#fff;text-align:left">
      <th>Destino</th><th>Precio</th><th>Fecha</th>
      <th>Aerolínea</th><th>Duración</th><th>Escalas</th>
    </tr>
    {''.join(rows)}
  </table>
  <p style="color:#888;font-size:12px;margin-top:16px">
    Precios de ida orientativos vía Google Flights / SerpApi.
    Los umbrales se ajustan en config.py.
  </p>
</body></html>"""

    return subject, html


def main():
    resumen, chollos = scan_all()
    subject, html = build_email(resumen, chollos)
    notifier.send_email(subject, html)


if __name__ == "__main__":
    main()

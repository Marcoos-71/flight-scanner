# ============================================================
#  scan_job.py — Escaneo único + página web + aviso por email
# ============================================================
#  Pensado para ejecutarse por cron (GitHub Actions) 2 veces
#  por semana. Escanea todos los destinos de config.WATCHLIST
#  en varias fechas (ida y vuelta), guarda en la BD y el histórico,
#  genera la página (docs/index.html) y envía un email-resumen.
#
#  Ejecutar a mano:  python scan_job.py
# ============================================================

import json
import os
from datetime import date, datetime, timedelta

import api
import config
import database
import history
import notifier

# Carpeta que publica GitHub Pages.
PAGE_PATH = os.path.join("docs", "index.html")

_MESES = ["ene", "feb", "mar", "abr", "may", "jun",
          "jul", "ago", "sep", "oct", "nov", "dic"]

# Paleta para las líneas de la gráfica.
_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"]


def _date_pairs():
    """Pares (ida, vuelta) 'YYYY-MM-DD'. Vuelta = ida + TRIP_LENGTH_DAYS."""
    today = date.today()
    pairs = []
    for d in config.SCAN_DATES_AHEAD:
        out = today + timedelta(days=d)
        back = out + timedelta(days=config.TRIP_LENGTH_DAYS)
        pairs.append((out.isoformat(), back.isoformat()))
    return pairs


def scan_all():
    """Escanea toda la watchlist. Devuelve (resumen, chollos).

    Cada fila de `resumen` incluye el desglose por fecha (`by_date`) y el
    mejor vuelo global (`best`). `chollos` = filas con best <= umbral.
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
        by_date = []
        best = None
        for out_date, return_date in pairs:
            flights = api.search_flight(config.ORIGIN, iata, out_date,
                                        return_date=return_date)
            database.save_flights(flights)
            cheapest = api.get_cheapest(flights)
            by_date.append({"out": out_date, "back": return_date,
                            "flight": cheapest})
            if cheapest and (best is None or cheapest["price"] < best["price"]):
                best = cheapest

        row = {
            "iata": iata,
            "label": label,
            "flag": config.DEST_FLAGS.get(iata, ""),
            "threshold": threshold,
            "by_date": by_date,
            "best": best,
            "is_deal": bool(best and best["price"] <= threshold),
        }

        if not best:
            print(f"[scan_job] {label}: sin resultados")
        else:
            print(f"[scan_job] {label}: mejor {best['price']:.0f}€ "
                  f"(umbral {threshold}€){'  ⭐ CHOLLO' if row['is_deal'] else ''}")

        resumen.append(row)
        if row["is_deal"]:
            chollos.append(row)

    return resumen, chollos


# ============================================================
#  Email (estático: sin JS ni gráficas)
# ============================================================

def _deals_html(chollos):
    """Lista de 'chollos' (vacío si no hay)."""
    if not chollos:
        return ""
    lines = "".join(
        f"<li><b>{r['flag']} {r['label']}</b>: {r['best']['price']:.0f}€ i/v "
        f"({r['best']['date']} → {r['best'].get('return_date', '?')}, "
        f"umbral {r['threshold']}€) — "
        f"<a href='{api.booking_link(r['best']['origin'], r['best']['destination'], r['best']['date'], r['best'].get('return_date'))}'>"
        f"comprar ✈</a></li>"
        for r in chollos
    )
    return f"<h3 style='color:#1a7a1a'>⭐ Chollos por debajo de tu umbral</h3><ul>{lines}</ul>"


def build_email(resumen, chollos):
    """Devuelve (asunto, html) del email-resumen."""
    today = date.today().isoformat()
    subject = (f"🛫 {len(chollos)} chollo(s) de vuelos — {today}" if chollos
               else f"🛫 Resumen de vuelos (sin chollos) — {today}")

    rows = []
    for r in sorted(resumen, key=lambda x: (x["best"] is None,
                                            x["best"]["price"] if x["best"] else 0)):
        f = r["best"]
        if not f:
            rows.append(f"<tr><td>{r['flag']} {r['label']}</td>"
                        f"<td colspan='5' style='color:#888'>sin resultados</td></tr>")
            continue
        bg = "background:#eafbea;" if r["is_deal"] else ""
        star = " ⭐" if r["is_deal"] else ""
        stops = "directo" if f["stops"] == 0 else f"{f['stops']} escala(s)"
        link = api.booking_link(f["origin"], f["destination"], f["date"],
                                f.get("return_date"))
        rows.append(
            f"<tr style='{bg}'><td>{r['flag']} {r['label']}{star}</td>"
            f"<td><b>{f['price']:.0f}€</b></td>"
            f"<td>{f['date']} → {f.get('return_date', '')}</td>"
            f"<td>{f['airline']}</td><td>{stops}</td>"
            f"<td><a href='{link}'>Comprar&nbsp;✈</a></td></tr>"
        )

    html = f"""\
<html><body style="font-family:system-ui,sans-serif;color:#222">
  <h2>🛫 Flight Scanner — {today}</h2>
  {_deals_html(chollos)}
  <h3>Ida y vuelta más barata por destino (viaje de {config.TRIP_LENGTH_DAYS} días)</h3>
  <table cellpadding="6" cellspacing="0"
         style="border-collapse:collapse;font-size:14px">
    <tr style="background:#1a3a5c;color:#fff;text-align:left">
      <th>Destino</th><th>Precio i/v</th><th>Fechas</th>
      <th>Aerolínea</th><th>Escalas</th><th>Reservar</th>
    </tr>
    {''.join(rows)}
  </table>
  <p style="color:#888;font-size:12px;margin-top:16px">
    Mira el dashboard completo (con gráfica de tendencia) en tu página de GitHub Pages.
  </p>
</body></html>"""
    return subject, html


# ============================================================
#  Página web (docs/index.html) — bonita e interactiva
# ============================================================

def _price_class(price, threshold):
    if price <= threshold:
        return "deal"
    if price <= threshold * 1.15:
        return "near"
    return ""


def _month_chips(row):
    """Chips con el precio de cada mes/fecha; resalta el más barato."""
    best_price = row["best"]["price"] if row["best"] else None
    chips = []
    for d in row["by_date"]:
        mes = _MESES[int(d["out"][5:7]) - 1]
        f = d["flight"]
        if not f:
            chips.append(f"<span class='chip'>{mes}: —</span>")
        else:
            cls = "chip best" if f["price"] == best_price else "chip"
            chips.append(f"<span class='{cls}'>{mes}: {f['price']:.0f}€</span>")
    return f"<div class='chips'>{''.join(chips)}</div>"


def _page_row(row):
    f = row["best"]
    label = f"<span class='flag'>{row['flag']}</span> {row['label']}"
    if not f:
        return (f"<tr data-deal='0' data-stops='9' data-price='999999' data-dur='999999'>"
                f"<td>{label}{_month_chips(row)}</td>"
                f"<td colspan='5' class='muted'>sin resultados</td></tr>")
    star = " ⭐" if row["is_deal"] else ""
    pc = _price_class(f["price"], row["threshold"])
    stops = "directo" if f["stops"] == 0 else f"{f['stops']} escala(s)"
    link = api.booking_link(f["origin"], f["destination"], f["date"],
                            f.get("return_date"))
    return (
        f"<tr data-deal='{1 if row['is_deal'] else 0}' data-stops='{f['stops']}' "
        f"data-price='{f['price']:.0f}' data-dur='{f.get('duration_minutes') or 0}'>"
        f"<td>{label}{star}{_month_chips(row)}</td>"
        f"<td class='price {pc}'>{f['price']:.0f}€</td>"
        f"<td>{f['date']} → {f.get('return_date', '')}</td>"
        f"<td>{f['airline']}</td>"
        f"<td>{f['duration']}</td>"
        f"<td>{stops}</td>"
        f"<td><a class='buy' href='{link}'>Comprar ✈</a></td></tr>"
    )


def _chart_json(hist):
    """Datos para Chart.js a partir del histórico."""
    labels_x = [s["ts"] for s in hist]
    datasets = []
    for i, (iata, label, _thr) in enumerate(config.WATCHLIST):
        color = _PALETTE[i % len(_PALETTE)]
        datasets.append({
            "label": f"{config.DEST_FLAGS.get(iata, '')} {label}",
            "data": [s["prices"].get(label) for s in hist],
            "borderColor": color,
            "backgroundColor": color,
            "tension": 0.25,
            "borderWidth": 2,
            "pointRadius": 2,
        })
    return json.dumps({"labels": labels_x, "datasets": datasets},
                      ensure_ascii=False)


def build_page(resumen, chollos, hist):
    """Página HTML autónoma para GitHub Pages (la que anclas en Firefox)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n = len(chollos)
    badge = (f"<span class='badge on'>{n} chollo(s)</span>" if n
             else "<span class='badge off'>sin chollos ahora</span>")

    rows = "".join(_page_row(r) for r in sorted(
        resumen, key=lambda x: (x["best"] is None,
                                x["best"]["price"] if x["best"] else 0)))

    deals = (f"<div class='card deals'>{_deals_html(chollos)}</div>"
             if chollos else "")

    if len(hist) >= 1:
        chart_block = "<canvas id='trend'></canvas>"
    else:
        chart_block = "<p class='muted'>La gráfica aparecerá tras el primer escaneo.</p>"

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🛫 Flight Scanner</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <style>{_PAGE_CSS}</style>
</head>
<body>
  <header><div class="wrap"><h1>🛫 Flight Scanner</h1></div></header>
  <div class="wrap">
    <p class="sub">Última actualización: <b>{now}</b> {badge}
      <span class="muted">· viaje de {config.TRIP_LENGTH_DAYS} días · ida y vuelta</span></p>

    {deals}

    <div class="card">
      <h2>Ida y vuelta más barata por destino</h2>
      <div class="controls">
        <button class="fbtn active" onclick="filterRows('all',this)">Todos</button>
        <button class="fbtn" onclick="filterRows('deals',this)">Solo chollos ⭐</button>
        <button class="fbtn" onclick="filterRows('direct',this)">Solo directos</button>
        <span class="muted" style="align-self:center">· clic en una cabecera para ordenar</span>
      </div>
      <table id="flights">
        <thead><tr>
          <th class="nosort">Destino</th>
          <th data-col="price" data-type="num" onclick="sortTable(this)">Precio i/v</th>
          <th class="nosort hide-sm">Fechas</th>
          <th class="nosort hide-sm">Aerolínea</th>
          <th data-col="dur" data-type="num" onclick="sortTable(this)" class="hide-sm">Duración</th>
          <th data-col="stops" data-type="num" onclick="sortTable(this)">Escalas</th>
          <th class="nosort">Reservar</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <div class="card">
      <h2>Evolución del precio (tendencia)</h2>
      {chart_block}
    </div>

    <p class="foot">Se actualiza automáticamente lunes y jueves. Precios de ida y
      vuelta orientativos vía Google Flights / SerpApi. Ajusta destinos y umbrales
      en config.py.</p>
  </div>
  <script>window.CHART_DATA = {_chart_json(hist)};</script>
  <script>{_PAGE_JS}</script>
</body></html>"""


def write_page(resumen, chollos, hist):
    """Genera docs/index.html para GitHub Pages."""
    os.makedirs(os.path.dirname(PAGE_PATH), exist_ok=True)
    with open(PAGE_PATH, "w", encoding="utf-8") as fh:
        fh.write(build_page(resumen, chollos, hist))
    print(f"[scan_job] Página generada en {PAGE_PATH}")


def main():
    resumen, chollos = scan_all()

    # Histórico (para la gráfica de tendencia)
    hist = history.load_history()
    prices = {r["label"]: (r["best"]["price"] if r["best"] else None)
              for r in resumen}
    hist = history.append_snapshot(hist, prices)
    history.save_history(hist)

    # Página web + email
    write_page(resumen, chollos, hist)
    subject, html = build_email(resumen, chollos)
    notifier.send_email(subject, html)


# CSS y JS como cadenas normales (NO f-strings) para no chocar con las llaves.
_PAGE_CSS = """
:root{--bg:#f4f6f9;--card:#fff;--text:#1f2933;--muted:#7b8794;--brand:#1a3a5c;
--green:#1a7a1a;--greenbg:#e7f7e7;--amber:#b8860b;--line:#e3e8ee;}
@media (prefers-color-scheme:dark){:root{--bg:#0f1620;--card:#16202c;--text:#e6edf3;
--muted:#90a0b0;--brand:#102a42;--green:#5fd35f;--greenbg:#15311a;--amber:#e3b341;
--line:#26303c;}}
*{box-sizing:border-box;}
body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
background:var(--bg);color:var(--text);margin:0;}
.wrap{max-width:1000px;margin:0 auto;padding:0 16px;}
header{background:var(--brand);color:#fff;padding:20px 0;border-radius:0 0 14px 14px;}
header h1{margin:0;font-size:26px;}
.sub{margin:16px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
.badge{padding:3px 10px;border-radius:20px;color:#fff;font-size:13px;font-weight:600;}
.badge.on{background:var(--green);}.badge.off{background:var(--muted);}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:16px 18px;margin:16px 0;box-shadow:0 1px 3px rgba(0,0,0,.05);}
h2{font-size:18px;margin:0 0 12px;}
.deals ul{margin:6px 0;padding-left:20px;}.deals li{margin:5px 0;}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;}
.fbtn{border:1px solid var(--line);background:var(--card);color:var(--text);
border-radius:20px;padding:6px 14px;cursor:pointer;font-size:13px;}
.fbtn.active{background:var(--brand);color:#fff;border-color:var(--brand);}
table{width:100%;border-collapse:collapse;font-size:14px;}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);
vertical-align:top;}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
cursor:pointer;user-select:none;white-space:nowrap;}
th.nosort{cursor:default;}
tbody tr:hover{background:rgba(127,127,127,.06);}
.flag{font-size:18px;}
.price{font-weight:700;font-size:15px;}
.price.deal{color:var(--green);}.price.near{color:var(--amber);}
.chips{margin-top:5px;display:flex;gap:5px;flex-wrap:wrap;}
.chip{font-size:11px;padding:2px 7px;border-radius:10px;background:var(--bg);
border:1px solid var(--line);color:var(--muted);}
.chip.best{background:var(--greenbg);color:var(--green);border-color:var(--green);
font-weight:600;}
.buy{color:var(--brand);text-decoration:none;font-weight:600;white-space:nowrap;}
.buy:hover{text-decoration:underline;}
.muted{color:var(--muted);}
canvas{max-height:340px;}
.foot{color:var(--muted);font-size:12px;margin:20px 0;}
@media(max-width:640px){.hide-sm{display:none;}}
"""

_PAGE_JS = """
function sortTable(th){
  const col=th.dataset.col, type=th.dataset.type||'str';
  const tb=document.querySelector('#flights tbody');
  const rows=[...tb.querySelectorAll('tr')];
  const asc=th.dataset.dir!=='asc';
  document.querySelectorAll('#flights th').forEach(h=>h.removeAttribute('data-dir'));
  th.dataset.dir=asc?'asc':'desc';
  rows.sort((a,b)=>{
    let x=a.dataset[col], y=b.dataset[col];
    if(type==='num'){x=parseFloat(x);y=parseFloat(y);}
    if(x<y)return asc?-1:1; if(x>y)return asc?1:-1; return 0;
  });
  rows.forEach(r=>tb.appendChild(r));
}
function filterRows(mode,btn){
  document.querySelectorAll('#flights tbody tr').forEach(r=>{
    let show=true;
    if(mode==='deals')show=r.dataset.deal==='1';
    else if(mode==='direct')show=r.dataset.stops==='0';
    r.style.display=show?'':'none';
  });
  document.querySelectorAll('.fbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
}
window.addEventListener('DOMContentLoaded',function(){
  if(window.CHART_DATA && CHART_DATA.labels.length){
    new Chart(document.getElementById('trend'),{
      type:'line',
      data:{labels:CHART_DATA.labels,datasets:CHART_DATA.datasets},
      options:{responsive:true,maintainAspectRatio:false,spanGaps:true,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{position:'bottom',labels:{boxWidth:12,font:{size:11}}}},
        scales:{y:{title:{display:true,text:'€ ida y vuelta'}}}}
    });
  }
});
"""


if __name__ == "__main__":
    main()

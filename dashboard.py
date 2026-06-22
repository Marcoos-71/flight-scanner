# ============================================================
#  dashboard.py — Interfaz visual (Dash / Plotly)
# ============================================================
#  Dashboard web local para buscar vuelos, ver los más baratos
#  (con y sin escalas), las alertas de precio y el historial.
#
#  Lanzar:   python dashboard.py
#  Abrir:    http://localhost:8050
# ============================================================

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, dash_table, Input, Output, State

import api
import config
import database


# Asegura que la BD y la tabla existen antes de arrancar.
database.init_db()

app = Dash(__name__)
app.title = "Flight Scanner"

# Códigos de aeropuerto de origen disponibles en el selector:
# los orígenes de ROUTES más MAD por defecto.
ORIGIN_OPTIONS = sorted({origin for origin, _, _ in config.ROUTES} | {"MAD"})

# Columnas que mostramos en la tabla de resultados.
TABLE_COLUMNS = [
    {"name": "Precio (€)", "id": "price"},
    {"name": "Aerolínea", "id": "airline"},
    {"name": "Duración", "id": "duration"},
    {"name": "Escalas", "id": "stops"},
    {"name": "Salida", "id": "departure"},
    {"name": "Llegada", "id": "arrival"},
    {"name": "Destino", "id": "destination"},
    {"name": "Fecha", "id": "date"},
]


# ============================================================
#  Layout
# ============================================================

app.layout = html.Div(
    style={"fontFamily": "system-ui, sans-serif", "margin": "0", "padding": "0"},
    children=[
        html.H1(
            "🛫 Flight Scanner",
            style={"background": "#1a3a5c", "color": "white",
                   "padding": "16px 24px", "margin": "0"},
        ),
        html.Div(
            style={"display": "flex", "gap": "24px", "padding": "24px"},
            children=[
                # ---------- Panel de búsqueda ----------
                html.Div(
                    style={"width": "260px", "flexShrink": "0"},
                    children=[
                        html.H3("Buscar"),

                        html.Label("Origen"),
                        dcc.Dropdown(
                            id="origin",
                            options=[{"label": o, "value": o} for o in ORIGIN_OPTIONS],
                            value="MAD",
                            clearable=False,
                        ),

                        html.Label("Región", style={"marginTop": "12px"}),
                        dcc.Dropdown(
                            id="region",
                            options=[{"label": r, "value": r} for r in config.REGIONS],
                            placeholder="(opcional) buscar por región",
                        ),

                        html.Label("Destino", style={"marginTop": "12px"}),
                        dcc.Input(
                            id="destination",
                            type="text",
                            placeholder="IATA, ej. BCN",
                            style={"width": "100%"},
                        ),
                        html.Small(
                            "Si eliges región, se ignora el destino.",
                            style={"color": "#888"},
                        ),

                        html.Label("Fecha de ida", style={"marginTop": "12px",
                                                          "display": "block"}),
                        dcc.DatePickerSingle(
                            id="date",
                            min_date_allowed=date.today(),
                            date=(date.today() + timedelta(days=30)),
                            display_format="YYYY-MM-DD",
                        ),

                        html.Label("Adultos", style={"marginTop": "12px",
                                                     "display": "block"}),
                        dcc.Input(
                            id="adults",
                            type="number",
                            min=1,
                            value=config.DEFAULT_ADULTS,
                            style={"width": "100%"},
                        ),

                        html.Button(
                            "Buscar",
                            id="search-btn",
                            n_clicks=0,
                            style={"marginTop": "16px", "width": "100%",
                                   "padding": "10px", "background": "#1a3a5c",
                                   "color": "white", "border": "none",
                                   "cursor": "pointer"},
                        ),

                        html.Hr(),
                        html.H4("Alertas activas"),
                        html.Div(id="alerts"),
                    ],
                ),

                # ---------- Resultados ----------
                html.Div(
                    style={"flexGrow": "1"},
                    children=[
                        html.H3("Resultados"),
                        html.Div(id="summary", style={"marginBottom": "12px"}),
                        dash_table.DataTable(
                            id="results-table",
                            columns=TABLE_COLUMNS,
                            data=[],
                            sort_action="native",
                            page_size=10,
                            style_cell={"textAlign": "left", "padding": "6px"},
                            style_header={"fontWeight": "bold",
                                          "background": "#eef2f6"},
                            style_data_conditional=[
                                {"if": {"filter_query": "{stops} = 0"},
                                 "backgroundColor": "#eafbea"},
                            ],
                        ),

                        html.H3("Historial de precios", style={"marginTop": "24px"}),
                        dcc.Graph(id="history-graph"),
                    ],
                ),
            ],
        ),

        # Refresco automático de las alertas.
        dcc.Interval(id="refresh", interval=5 * 60 * 1000),  # 5 min
    ],
)


# ============================================================
#  Callbacks
# ============================================================

@app.callback(
    Output("results-table", "data"),
    Output("summary", "children"),
    Output("history-graph", "figure"),
    Input("search-btn", "n_clicks"),
    State("origin", "value"),
    State("region", "value"),
    State("destination", "value"),
    State("date", "date"),
    State("adults", "value"),
    prevent_initial_call=True,
)
def do_search(_n_clicks, origin, region, destination, flight_date, adults):
    """Ejecuta la búsqueda, guarda en BD y actualiza tabla, resumen y gráfica."""
    flight_date = (flight_date or "").split("T")[0]  # DatePicker da ISO completo

    if region:
        flights = api.search_region(origin, region, flight_date)
        title = f"{origin} → {region}"
    elif destination:
        destination = destination.strip().upper()
        flights = api.search_flight(origin, destination, flight_date,
                                    adults or config.DEFAULT_ADULTS)
        title = f"{origin} → {destination}"
    else:
        return [], html.Span("Indica un destino o una región.",
                             style={"color": "#c00"}), _empty_figure()

    # Persistimos lo encontrado para alimentar el historial.
    database.save_flights(flights)

    resumen = api.summarize(flights)
    summary_children = _build_summary(resumen, title)
    figure = _build_history_figure(origin, destination if not region else None)

    return resumen["all"], summary_children, figure


@app.callback(
    Output("alerts", "children"),
    Input("refresh", "n_intervals"),
    Input("search-btn", "n_clicks"),
)
def update_alerts(_n_intervals, _n_clicks):
    """Muestra 🟢/🔴 por cada ruta según el umbral de PRICE_ALERTS."""
    items = []
    for origin, destination, label in config.ROUTES:
        threshold = config.PRICE_ALERTS.get(label)
        cheapest = database.get_cheapest_ever(origin, destination)

        if not cheapest:
            items.append(html.Div(f"⚪ {label}: sin datos"))
            continue

        price = cheapest["price"]
        if threshold is not None and price <= threshold:
            icon, color = "🔴", "#c00"  # ¡chollo! por debajo del umbral
            note = f"{price:.0f}€ ≤ {threshold}€"
        else:
            icon, color = "🟢", "#2a7"
            note = f"{price:.0f}€"
            if threshold is not None:
                note += f" (alerta < {threshold}€)"

        items.append(
            html.Div(f"{icon} {label}: {note}",
                     style={"color": color, "marginBottom": "4px"})
        )
    return items


# ============================================================
#  Helpers
# ============================================================

def _build_summary(resumen, title):
    """Tarjetas de texto con el más barato y el más barato sin escalas."""
    cheapest = resumen["cheapest"]
    nonstop = resumen["cheapest_nonstop"]

    if not cheapest:
        return html.Span(f"Sin resultados para {title}.", style={"color": "#c00"})

    def card(label, f):
        if not f:
            return html.Div(f"{label}: no disponible", style={"color": "#888"})
        return html.Div(
            f"{label}: {f['price']:.0f}€ · {f['airline']} · "
            f"{f['duration']} · {f['stops']} escala(s) · "
            f"{f['origin']}→{f['destination']}",
            style={"fontWeight": "bold"},
        )

    return html.Div([
        html.Div(title, style={"fontSize": "18px", "marginBottom": "6px"}),
        card("💶 Más barato", cheapest),
        card("✈️ Más barato sin escalas", nonstop),
    ])


def _build_history_figure(origin, destination):
    """Gráfica de línea: evolución del precio mínimo de la ruta en el tiempo."""
    if not destination:
        return _empty_figure("Busca una ruta concreta para ver su historial.")

    df = database.get_history(origin, destination, days=30)
    if df.empty:
        return _empty_figure("Aún no hay historial para esta ruta.")

    # Precio mínimo por cada escaneo (timestamp).
    grouped = (
        df.groupby("scanned_at", as_index=False)["price"].min()
        .sort_values("scanned_at")
    )
    grouped["scanned_at"] = pd.to_datetime(grouped["scanned_at"])

    fig = px.line(
        grouped, x="scanned_at", y="price", markers=True,
        title=f"Precio mínimo {origin}→{destination} (últimos 30 días)",
        labels={"scanned_at": "Fecha de escaneo", "price": "Precio (€)"},
    )
    fig.update_layout(margin={"t": 50, "l": 20, "r": 20, "b": 20})
    return fig


def _empty_figure(message="Sin datos"):
    """Figura vacía con un mensaje centrado."""
    fig = px.line()
    fig.update_layout(
        annotations=[{
            "text": message, "showarrow": False,
            "xref": "paper", "yref": "paper", "x": 0.5, "y": 0.5,
            "font": {"size": 14, "color": "#888"},
        }],
        xaxis={"visible": False}, yaxis={"visible": False},
        margin={"t": 20, "l": 20, "r": 20, "b": 20},
    )
    return fig


if __name__ == "__main__":
    app.run(debug=True, port=8050)

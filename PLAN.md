# 🛫 Flight Scanner — Plan de desarrollo

> Proyecto: scanner de precios de vuelos con dashboard visual  
> Stack: Python · SerpApi · SQLite · Dash/Plotly  
> Estado actual: `config.py` creado ✅

---

## Estado del proyecto

```
flight_scanner/
├── config.py       ✅ Creado — API key, rutas, regiones, alertas
├── api.py          ⬜ Pendiente
├── database.py     ⬜ Pendiente
├── scheduler.py    ⬜ Pendiente
├── dashboard.py    ⬜ Pendiente
└── requirements.txt ⬜ Pendiente
```

---

## Setup inicial

### 1. Dependencias

```bash
pip install dash plotly pandas requests schedule google-search-results
```

### 2. API Key

Abre `config.py` y reemplaza `"TU_API_KEY_AQUI"` con tu key real de SerpApi:  
→ https://serpapi.com/manage-api-key

---

## Módulos a desarrollar

### Módulo 1 — `api.py` (llamadas a SerpApi)

**Objetivo:** consultar precios de vuelos a través de Google Flights vía SerpApi.

**Funciones a implementar:**

```python
search_flight(origin, destination, date, adults) -> list[dict]
# Devuelve lista de vuelos con precio, aerolínea, duración, escalas

search_region(origin, region_name, date) -> list[dict]
# Llama a search_flight para cada destino de la región
# y devuelve todos los resultados ordenados por precio

get_cheapest(results) -> dict
# Filtra el vuelo más barato de una lista de resultados
```

**Parámetros clave de SerpApi (Google Flights):**
- `engine`: `"google_flights"`
- `departure_id`: código IATA origen (ej. `"MAD"`)
- `arrival_id`: código IATA destino (ej. `"BCN"`)
- `outbound_date`: formato `"YYYY-MM-DD"`
- `currency`: `"EUR"`
- `hl`: `"es"`

**Ejemplo de respuesta esperada:**
```json
{
  "price": 34,
  "airline": "Vueling",
  "duration": "1h 25m",
  "stops": 0,
  "departure": "07:30",
  "arrival": "08:55",
  "origin": "MAD",
  "destination": "BCN",
  "date": "2026-07-15"
}
```

---

### Módulo 2 — `database.py` (historial SQLite)

**Objetivo:** guardar cada búsqueda para poder ver la evolución del precio en el tiempo.

**Funciones a implementar:**

```python
init_db()
# Crea la base de datos y la tabla si no existen

save_flights(flights: list[dict])
# Inserta los vuelos encontrados en la BD con timestamp

get_history(origin, destination, days=30) -> pd.DataFrame
# Devuelve el historial de precios de una ruta en los últimos N días

get_cheapest_ever(origin, destination) -> dict
# Devuelve el vuelo más barato registrado para esa ruta
```

**Esquema de la tabla `flights`:**

| columna | tipo | descripción |
|---|---|---|
| `id` | INTEGER PK | autoincremental |
| `origin` | TEXT | código IATA origen |
| `destination` | TEXT | código IATA destino |
| `date` | TEXT | fecha del vuelo |
| `price` | REAL | precio en EUR |
| `airline` | TEXT | aerolínea |
| `duration` | TEXT | duración del vuelo |
| `stops` | INTEGER | número de escalas |
| `departure` | TEXT | hora de salida |
| `arrival` | TEXT | hora de llegada |
| `scanned_at` | TEXT | timestamp del escaneo |

---

### Módulo 3 — `scheduler.py` (escaneo automático)

**Objetivo:** ejecutar búsquedas periódicamente en segundo plano sin intervención manual.

**Funciones a implementar:**

```python
run_scan()
# Lanza search_flight para todas las rutas en ROUTES
# y las guarda en BD vía save_flights()

start_scheduler()
# Lanza run_scan() cada SCAN_INTERVAL_HOURS horas (configurado en config.py)
# usando la librería `schedule`
```

**Flujo:**
```
start_scheduler()
    └─ cada 6h → run_scan()
                    ├─ busca MAD→BCN, guarda en BD
                    ├─ busca MAD→LIS, guarda en BD
                    └─ busca MAD→ROM, guarda en BD
```

---

### Módulo 4 — `dashboard.py` (interfaz visual)

**Objetivo:** visualizar precios, historial y alertas en un dashboard web local.

**Layout del dashboard (Dash):**

```
┌─────────────────────────────────────────────────┐
│  🛫 Flight Scanner                               │
├──────────────┬──────────────────────────────────┤
│ BUSCAR       │  RESULTADOS                      │
│              │                                  │
│ Origen       │  Tabla: vuelos más baratos       │
│ Destino /    │  (precio, aerolínea, fecha,      │
│ Región       │   duración, escalas)             │
│ Fecha ida    │                                  │
│ Fecha vuelta │  ── Alertas activas ──           │
│ Adultos      │  🟢 / 🔴 por ruta               │
│              │                                  │
│ [Buscar]     ├──────────────────────────────────┤
│              │  HISTORIAL DE PRECIOS            │
│              │  Gráfica línea: evolución        │
│              │  del precio mínimo por ruta      │
└──────────────┴──────────────────────────────────┘
```

**Componentes Dash a usar:**
- `dcc.Dropdown` → selector de origen, destino y región
- `dcc.DatePickerSingle` → fecha del vuelo
- `dash_table.DataTable` → tabla de resultados
- `dcc.Graph` → gráfica de historial (Plotly line chart)
- `dcc.Interval` → refresco automático del dashboard cada X minutos

---

### Archivo — `requirements.txt`

```
dash>=2.14
plotly>=5.18
pandas>=2.0
requests>=2.31
schedule>=1.2
google-search-results>=2.4
```

---

## Orden de implementación recomendado

1. **`requirements.txt`** — instalar todo primero
2. **`api.py`** — sin esto no hay datos; probarlo con una búsqueda manual antes de seguir
3. **`database.py`** — guardar los resultados de api.py
4. **`scheduler.py`** — automatizar el escaneo
5. **`dashboard.py`** — visualizar todo

> 💡 Tip: después de crear `api.py`, pruébalo en un script rápido `test_api.py` antes de integrarlo con la BD, para verificar que SerpApi devuelve los datos esperados.

---

## Cómo lanzar el proyecto (cuando esté completo)

```bash
# En una terminal: lanza el scanner automático
python scheduler.py

# En otra terminal: lanza el dashboard
python dashboard.py

# Abre en el navegador:
# http://localhost:8050
```

---

## Referencias útiles

- SerpApi Google Flights docs: https://serpapi.com/google-flights-api
- Códigos IATA de aeropuertos: https://www.iata.org/en/publications/directories/code-search/
- Dash documentación: https://dash.plotly.com/
- SQLite con Python: https://docs.python.org/3/library/sqlite3.html

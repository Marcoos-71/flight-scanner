# ============================================================
#  history.py — Histórico de precios para la gráfica de tendencia
# ============================================================
#  Guarda, por cada escaneo, el precio más barato de cada ruta en
#  un JSON que se sube al repo (sobrevive entre ejecuciones en la
#  nube). Así la página puede dibujar la evolución en el tiempo.
# ============================================================

import json
import os
from datetime import date

import config

# Máximo de snapshots a conservar (~1 año a 2/semana).
MAX_SNAPSHOTS = 120


def load_history():
    """Carga el histórico (lista de snapshots). Lista vacía si no existe."""
    path = config.HISTORY_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def append_snapshot(history, prices):
    """Añade (o reemplaza si es del mismo día) un snapshot {ts, prices}.

    `prices` es {etiqueta_ruta: precio_o_None}. Devuelve el histórico
    recortado a los últimos MAX_SNAPSHOTS.
    """
    snapshot = {"ts": date.today().isoformat(), "prices": prices}
    if history and history[-1].get("ts") == snapshot["ts"]:
        history[-1] = snapshot
    else:
        history.append(snapshot)
    return history[-MAX_SNAPSHOTS:]


def save_history(history):
    """Guarda el histórico en disco."""
    folder = os.path.dirname(config.HISTORY_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(config.HISTORY_PATH, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False)

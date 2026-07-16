"""
warming_stripes.py -- Standalone full-screen Climate Warming Stripes app.

Run:
    streamlit run warming_stripes.py

The HTML component is served from a background thread via a custom HTTP handler
that also exposes /api/era5/ routes so the JS can read local ERA5 Italy parquets
without hitting Open-Meteo at all for Italian cities.
"""
import http.server
import json
import math
import socket
import threading
import urllib.parse
from functools import partial
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT        = Path(__file__).parent
_PAGES_DIR  = ROOT / "pages"
_ERA5_DIR   = ROOT / "data" / "era5_italy"
_INDEX_JSON = ROOT / "data" / "04_parquet" / "index.json"
_STATIC_PORT = 8594

# ── ERA5 station index (built once, shared across requests) ───────────────────
_STATION_INDEX: list[dict] | None = None
_INDEX_LOCK = threading.Lock()


def _build_station_index() -> list[dict]:
    """Build lat/lon -> station_id lookup from FWA index, filtered to stations
    that have an ERA5 parquet on disk."""
    global _STATION_INDEX
    with _INDEX_LOCK:
        if _STATION_INDEX is not None:
            return _STATION_INDEX
        if not _INDEX_JSON.exists() or not _ERA5_DIR.exists():
            _STATION_INDEX = []
            return _STATION_INDEX
        raw = json.loads(_INDEX_JSON.read_text(encoding="utf-8"))
        seen: dict[str, dict] = {}
        for e in raw:
            if e.get("country") != "ITA":
                continue
            sid = e.get("station_id", "")
            if not sid or sid in seen:
                continue
            pq = _ERA5_DIR / f"{sid}.parquet"
            if not pq.exists():
                continue
            lat = e.get("latitude")
            lon = e.get("longitude")
            if lat is None or lon is None:
                continue
            seen[sid] = {
                "id":   sid,
                "name": e.get("location_name", sid),
                "lat":  float(lat),
                "lon":  float(lon),
            }
        _STATION_INDEX = list(seen.values())
        return _STATION_INDEX


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Custom HTTP handler ───────────────────────────────────────────────────────
class _Era5Handler(http.server.SimpleHTTPRequestHandler):
    """Serves static files from _PAGES_DIR plus:
      GET /api/era5/search?lat=X&lon=Y  -> nearest Italian ERA5 station (JSON) or null
      GET /api/era5/data?id=STATION_ID  -> full daily data (JSON)
    """

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/era5/search":
            self._search(parsed.query)
        elif parsed.path == "/api/era5/data":
            self._data(parsed.query)
        else:
            super().do_GET()

    # ── /api/era5/search ──────────────────────────────────────────────────────
    def _search(self, query: str):
        params = urllib.parse.parse_qs(query)
        try:
            lat = float(params["lat"][0])
            lon = float(params["lon"][0])
        except (KeyError, ValueError):
            self._json({"error": "lat and lon required"}, 400)
            return

        stations = _build_station_index()
        best = None
        best_km = float("inf")
        for s in stations:
            km = _haversine_km(lat, lon, s["lat"], s["lon"])
            if km < best_km:
                best_km = km
                best = s

        # Accept match within 30 km (ERA5 at 0.25deg ~ 28 km)
        self._json(best if best and best_km <= 30 else None)

    # ── /api/era5/data ────────────────────────────────────────────────────────
    def _data(self, query: str):
        params = urllib.parse.parse_qs(query)
        sid = params.get("id", [""])[0]
        pq  = _ERA5_DIR / f"{sid}.parquet"
        if not pq.exists():
            self._json({"error": "station not found"}, 404)
            return

        df = pd.read_parquet(pq)
        df = df.dropna(how="all")
        self._json({
            "station_id": sid,
            "dates": df.index.strftime("%Y-%m-%d").tolist(),
            "mean":  [round(v, 3) if pd.notna(v) else None for v in df["t_mean"]],
            "max":   [round(v, 3) if pd.notna(v) else None for v in df["t_max"]],
            "min":   [round(v, 3) if pd.notna(v) else None for v in df["t_min"]],
        })

    # ── helpers ───────────────────────────────────────────────────────────────
    def _json(self, data, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


# ── Server startup ────────────────────────────────────────────────────────────
def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def _ensure_static_server() -> None:
    if not _port_free(_STATIC_PORT):
        return
    handler = partial(_Era5Handler, directory=str(_PAGES_DIR))
    try:
        server = http.server.HTTPServer(("localhost", _STATIC_PORT), handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        # Warm up the station index in background so first search is instant
        threading.Thread(target=_build_station_index, daemon=True).start()
    except OSError:
        pass


import os
import streamlit.components.v1 as components

# Only start the local API server when actually running locally. On Streamlit
# Cloud (or any host where the browser and the Python process are different
# machines), "localhost" in the browser means the VISITOR'S machine, not the
# server -- so an <iframe src="http://localhost:PORT"> can never resolve
# there. Set WARMINGSTRIPES_LOCAL=1 in your local shell to enable it.
_RUNNING_LOCALLY = os.environ.get("WARMINGSTRIPES_LOCAL") == "1"
if _RUNNING_LOCALLY:
    _ensure_static_server()

# ── Streamlit page ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EETRA Warming Stripes",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
header[data-testid="stHeader"], footer, #MainMenu, .stDeployButton { display:none!important }
html, body, .stApp { background:#0b0b0c!important; margin:0; padding:0; overflow:hidden }
[data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMain"] > div, .stMainBlockContainer, .block-container {
  padding:0!important; margin:0!important; max-width:100%!important; overflow:hidden!important }
iframe { position:fixed!important; top:0!important; left:0!important;
         width:100vw!important; height:100vh!important; border:none!important; z-index:9999!important }
</style>""", unsafe_allow_html=True)

# Embed the HTML directly via srcdoc (components.html) instead of pointing an
# iframe at an external "http://localhost:PORT" URL. This works identically
# locally and on Streamlit Cloud -- no separate server or port needed for the
# page to load at all. The page's own JS already targets
# `window.location.origin` for the optional local ERA5 fast-path and falls
# back to Open-Meteo automatically if that route 404s, so nothing else here
# needs to change.
_html_content = (_PAGES_DIR / "_thermachrome.html").read_text(encoding="utf-8")
components.html(_html_content, height=1000, scrolling=False)
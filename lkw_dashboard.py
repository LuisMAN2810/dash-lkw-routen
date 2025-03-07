import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
import requests
import json
import polyline
import os
import re
import time
from flask import Flask

# OpenRouteService API-Key
ORS_API_KEY = "5b3ce3597851110001cf6248f42ededae9b5414fb25591adaff63db4"

# Flask-Server erstellen, um HEAD-Requests zu unterstützen
server = Flask(__name__)
app = dash.Dash(__name__, server=server, suppress_callback_exceptions=True)

@server.route("/", methods=["HEAD"])
def head_request():
    return "", 200

# CSV-Datei einlesen
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8-sig")

df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')
df = df.dropna(subset=["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Route"])

def clean_coordinates(coord_string):
    try:
        if isinstance(coord_string, str):
            coord_string = re.sub(r'[^0-9.,\s-]', '', coord_string)
            coord_string = coord_string.replace("\t", "").replace(" ", "").strip()
            coord_string = re.sub(r'\.\.', '.', coord_string)
            coord_string = coord_string.replace(";", ",")
            parts = coord_string.split(",")
            if len(parts) == 2:
                lon, lat = map(float, parts)
                return [lon, lat]
    except Exception as e:
        print(f"⚠️ Fehler bei der Umwandlung der Koordinaten '{coord_string}': {e}")
    return None

df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)
df.dropna(subset=["Koordinaten Start", "Koordinaten Ziel"], inplace=True)

# Dropdown-Optionen mit Spalte "Route"
route_options = [{'label': route, 'value': route} for route in df['Route'].unique()]
route_options.insert(0, {'label': 'Alle Routen', 'value': 'all'})

# Caching für Routen
route_cache_file = "routes_cache.json"
if not os.path.exists(route_cache_file):
    with open(route_cache_file, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4)

try:
    with open(route_cache_file, "r", encoding="utf-8") as f:
        route_cache = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    route_cache = {}

MAX_CACHE_SIZE = 1000  # Begrenzung der gespeicherten Routen

def save_routes():
    if len(route_cache) > MAX_CACHE_SIZE:
        keys_to_remove = list(route_cache.keys())[:len(route_cache) - MAX_CACHE_SIZE]
        for key in keys_to_remove:
            del route_cache[key]
    with open(route_cache_file, "w", encoding="utf-8") as f:
        json.dump(route_cache, f, indent=4)

def get_lkw_route(start_coords, end_coords, route_name):
    if not start_coords or not end_coords:
        return None
    
    if route_name in route_cache:
        return route_cache[route_name]
    
    url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    data = {"coordinates": [start_coords, end_coords], "format": "json"}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            route_geometry = polyline.decode(data["routes"][0]["geometry"])
            route_cache[route_name] = route_geometry
            save_routes()
            return route_geometry
        else:
            print(f"⚠️ API-Fehler für {route_name}: {response.text}")
    except requests.exceptions.Timeout:
        print(f"⚠️ API-Timeout für {route_name}")
    except Exception as e:
        print(f"⚠️ API-Verbindungsfehler für {route_name}: {e}")
    return None

app.layout = html.Div([
    html.H1("LKW Routen-Dashboard"),
    dcc.Dropdown(id='route-selector', options=route_options, multi=True, value=['all'], placeholder="Wähle eine Route"),
    html.Iframe(id="map", width="100%", height="600")
])

@app.callback(Output('map', 'srcDoc'), [Input('route-selector', 'value')])
def update_map(selected_routes):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].dropna().tolist()
    
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)
    add_legend(m)
    
    for _, row in df.iterrows():
        if row["Route"] not in selected_routes:
            continue
        if row["Koordinaten Start"] is None or row["Koordinaten Ziel"] is None:
            continue
        route_geometry = get_lkw_route(row["Koordinaten Start"], row["Koordinaten Ziel"], row["Route"])
        if not route_geometry:
            continue
        folium.PolyLine(route_geometry, color=get_route_color(row["Transporte pro Woche"]), weight=5).add_to(m)
    
    return m._repr_html_()

if __name__ == '__main__':
    app.run_server(debug=False)

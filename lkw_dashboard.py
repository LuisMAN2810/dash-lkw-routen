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
df = df.dropna(subset=["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Routen Google Maps"])

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

# Dropdown-Optionen vorbereiten
route_options = [{'label': route, 'value': route} for route in df['Routen Google Maps'].unique()]
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

# Dash App Layout
def get_route_color(transporte):
    if transporte <= 10:
        return "green"
    elif transporte <= 50:
        return "yellow"
    elif transporte <= 100:
        return "orange"
    return "red"

def add_legend(m):
    legend_html = '''
     <div style="position: fixed; bottom: 50px; left: 50px; width: 220px; padding: 15px; background-color: white; 
     box-shadow: 2px 2px 10px rgba(0,0,0,0.3); z-index:9999; border-radius:10px; font-family:Arial;">
     <h4 style="margin: 0 0 10px 0; text-align:center;">Transporte pro Woche</h4>
     <div style="display: flex; align-items: center; margin-bottom: 5px;">
       <div style="width: 30px; height: 5px; background-color: green; margin-right: 10px;"></div>
       <span>1-10 Transporte</span>
     </div>
     <div style="display: flex; align-items: center; margin-bottom: 5px;">
       <div style="width: 30px; height: 5px; background-color: yellow; margin-right: 10px;"></div>
       <span>11-50 Transporte</span>
     </div>
     <div style="display: flex; align-items: center; margin-bottom: 5px;">
       <div style="width: 30px; height: 5px; background-color: orange; margin-right: 10px;"></div>
       <span>51-100 Transporte</span>
     </div>
     <div style="display: flex; align-items: center;">
       <div style="width: 30px; height: 5px; background-color: red; margin-right: 10px;"></div>
       <span>>100 Transporte</span>
     </div>
     </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

app.layout = html.Div([
    html.H1("LKW Routen-Dashboard"),
    dcc.Dropdown(id='route-selector', options=route_options, multi=True, value=['all'], placeholder="Wähle eine Route"),
    html.Iframe(id="map", width="100%", height="600")
])

@app.callback(Output('map', 'srcDoc'), [Input('route-selector', 'value')])
def update_map(selected_routes):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Routen Google Maps'].tolist()
    
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)
    add_legend(m)
    
    for _, row in df.iterrows():
        if row["Routen Google Maps"] in selected_routes:
            route_geometry = get_lkw_route(row["Koordinaten Start"], row["Koordinaten Ziel"], row["Routen Google Maps"])
            if route_geometry:
                folium.PolyLine(route_geometry, color=get_route_color(row["Transporte pro Woche"]), weight=5).add_to(m)
    
    return m._repr_html_()

if __name__ == '__main__':
    app.run_server(debug=False)

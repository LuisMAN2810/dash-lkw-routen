import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
import requests
import json

# GraphHopper API-Key
GRAPHHOPPER_API_KEY = "045abf50-4e22-453a-b0a9-8374930f4e47"

# Einlesen der CSV-Datei
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8")

# Spalten prüfen
required_columns = ["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Routen Google Maps"]
if not all(col in df.columns for col in required_columns):
    raise ValueError("Eine oder mehrere Spalten fehlen in der CSV-Datei!")

# Umwandlung der Transporte-Spalte
df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')

# Entfernen von NaN-Werten
df.dropna(subset=required_columns, inplace=True)

# Funktion zur Bereinigung der Koordinaten
def clean_coordinates(coord_string):
    try:
        if isinstance(coord_string, str):
            coord_string = coord_string.replace("\t", "").replace(",", ".").strip()
            lat, lon = map(float, coord_string.split(";"))
            return [lon, lat]
    except Exception as e:
        print(f"⚠️ Fehler bei der Koordinatenumwandlung: {e}")
    return None

# Koordinaten bereinigen
df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)

# Entfernen von fehlerhaften Koordinaten
df.dropna(subset=["Koordinaten Start", "Koordinaten Ziel"], inplace=True)

# Dash-App initialisieren
app = dash.Dash(__name__)

# Dropdown-Optionen erstellen
route_options = [{'label': 'Alle anzeigen', 'value': 'all'}] + [
    {'label': f"Route {index}", 'value': index} for index, row in df.iterrows()
]

# Layout der App
app.layout = html.Div([
    html.H1("LKW Routen-Dashboard"),
    dcc.Dropdown(
        id='route-selector',
        options=route_options,
        multi=True,
        placeholder="Wähle eine Route"
    ),
    html.Iframe(id="map", width="100%", height="600")
])

# GraphHopper API-Abfrage
def get_lkw_route(start_coords, end_coords):
    url = "https://graphhopper.com/api/1/route"
    params = {
        "key": GRAPHHOPPER_API_KEY,
        "point": [f"{start_coords[1]},{start_coords[0]}", f"{end_coords[1]},{end_coords[0]}"],
        "profile": "truck",
        "locale": "de",
        "calc_points": True,
        "instructions": False,
        "geometry_format": "geojson"
    }
    try:
        response = requests.get(url, params=params)
        print(f"🔹 API Request sent with coordinates: {start_coords} -> {end_coords}")
        if response.status_code == 200:
            data = response.json()
            if "paths" in data and data["paths"]:
                return data["paths"][0]["points"]
        else:
            print(f"❌ Fehler bei der API-Abfrage: {response.text}")
            return None
    except json.JSONDecodeError as json_error:
        print(f"🚫 JSON-Fehler beim Verarbeiten der API-Antwort: {json_error}")
        return None
    except Exception as e:
        print(f"⚠️ Unerwarteter Fehler: {e}")
        return None

# Routenfarbe bestimmen
def get_route_color(transporte):
    if transporte <= 10:
        return "green"
    elif transporte <= 50:
        return "yellow"
    elif transporte <= 100:
        return "orange"
    else:
        return "red"

# Callback zur Aktualisierung der Karte
@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value')]
)
def update_map(selected_routes):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df.index.tolist()

    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    for index, row in df.iterrows():
        if index in selected_routes:
            start_coords = row["Koordinaten Start"]
            end_coords = row["Koordinaten Ziel"]
            transporte = row["Transporte pro Woche"]

            if start_coords and end_coords:
                route_geometry = get_lkw_route(start_coords, end_coords)
                if route_geometry:
                    route_coords = route_geometry['coordinates'] if isinstance(route_geometry, dict) else json.loads(json.dumps(route_geometry))["coordinates"]
                    route_color = get_route_color(transporte)
                    folium.PolyLine(
                        locations=[[lat, lon] for lon, lat in route_coords],
                        color=route_color,
                        weight=5,
                        opacity=0.8
                    ).add_to(m)

    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

# Server starten
if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

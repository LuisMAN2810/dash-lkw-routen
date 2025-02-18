import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
import requests
import json
import polyline
from collections import defaultdict

# GraphHopper API-Key (ersetze mit deinem eigenen)
GRAPHHOPPER_API_KEY = "045abf50-4e22-453a-b0a9-8374930f4e47"

# CSV-Datei einlesen
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8")

# Spalten bereinigen
df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')
df = df.dropna(subset=["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Routen Google Maps"])

# Funktion zur Bereinigung der Koordinaten
def clean_coordinates(coord_string):
    try:
        if isinstance(coord_string, str):
            coord_string = coord_string.replace("\t", "").replace(",", ".").strip()
            lat, lon = map(float, coord_string.split(";"))
            return [lon, lat]
    except Exception as e:
        print(f"⚠️ Fehler bei der Umwandlung der Koordinaten '{coord_string}': {e}")
    return None

df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)
df.dropna(subset=["Koordinaten Start", "Koordinaten Ziel"], inplace=True)

# Dash-App initialisieren
app = dash.Dash(__name__)

route_options = [{'label': 'Alle anzeigen', 'value': 'all'}] + [
    {'label': row['Route'], 'value': row['Route']} for _, row in df.iterrows()
]

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

# API-Abfrage
def get_lkw_route(start_coords, end_coords):
    url = "https://graphhopper.com/api/1/route"
    params = {
        "key": GRAPHHOPPER_API_KEY,
        "point": [f"{start_coords[1]},{start_coords[0]}", f"{end_coords[1]},{end_coords[0]}"],
        "profile": "truck",
        "locale": "de",
        "calc_points": True,
        "instructions": False,
        "geometry": True
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return polyline.decode(data["paths"][0]["points"])
        else:
            print(f"⚠️ API-Fehler: {response.text}")
    except Exception as e:
        print(f"⚠️ API-Verbindungsfehler: {e}")
    return None

# Farben nach Transportmenge
def get_route_color(transporte):
    if transporte <= 10:
        return "green"
    elif transporte <= 50:
        return "yellow"
    elif transporte <= 100:
        return "orange"
    return "red"

@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value')]
)
def update_map(selected_routes):
    print("🔍 update_map() wurde aufgerufen")

    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].tolist()
    
    print(f"📌 Gewählte Routen: {selected_routes}")

    # Erstelle eine Karte
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    for _, row in df.iterrows():
        if row['Route'] in selected_routes:
            start_coords = row["Koordinaten Start"]
            end_coords = row["Koordinaten Ziel"]
            transporte = row["Transporte pro Woche"]
            google_maps_link = row["Routen Google Maps"]

            print(f"🚚 Verarbeite Route: {row['Route']} mit {transporte} Transporten")
            
            route_geometry = get_lkw_route(start_coords, end_coords)
            if route_geometry:
                folium.PolyLine(
                    route_geometry, 
                    color=get_route_color(transporte), 
                    weight=5, 
                    tooltip=folium.Tooltip(f"Transporte: {transporte}")
                ).add_to(m)

                folium.Marker(
                    location=[start_coords[1], start_coords[0]],
                    popup=folium.Popup(f"<b>Start</b><br><a href='{google_maps_link}' target='_blank'>Google Maps</a>", max_width=300),
                    icon=folium.Icon(color="blue")
                ).add_to(m)

                folium.Marker(
                    location=[end_coords[1], end_coords[0]],
                    popup=folium.Popup(f"<b>Ziel</b><br><a href='{google_maps_link}' target='_blank'>Google Maps</a>", max_width=300),
                    icon=folium.Icon(color="red")
                ).add_to(m)

    # Karte speichern
    try:
        map_path = "map.html"
        m.save(map_path)
        print(f"✅ Karte gespeichert unter {map_path}")
        return open(map_path, "r", encoding="utf-8").read()
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Karte: {e}")
        return ""

if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

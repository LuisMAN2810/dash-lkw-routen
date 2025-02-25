import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
from folium.plugins import HeatMap
import numpy as np
import requests
import polyline

# GraphHopper API-Key
GRAPHHOPPER_API_KEY = "045abf50-4e22-453a-b0a9-8374930f4e47"

# Cache für bereits berechnete Routen
route_cache = {}

# CSV-Datei einlesen
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8-sig")
df.columns = df.columns.str.strip()

# Rename der falschen Spalte
if 'ï»¿Route' in df.columns:
    df = df.rename(columns={'ï»¿Route': 'Route'})

# Funktion zur Bereinigung der Koordinaten
def clean_coordinates(coord_string):
    try:
        if isinstance(coord_string, str):
            coord_string = coord_string.replace("\t", "").replace(",", ".").strip()
            lat, lon = map(float, coord_string.split(";"))
            return [lat, lon]
    except Exception as e:
        print(f"⚠️ Fehler bei der Umwandlung der Koordinaten '{coord_string}': {e}")
    return None

# Daten bereinigen
df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')
df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)
df.dropna(subset=["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Routen Google Maps"], inplace=True)

# Funktion zur Routenberechnung mit Cache
def get_lkw_route(start_coords, end_coords):
    key = (tuple(start_coords), tuple(end_coords))
    if key in route_cache:
        return route_cache[key]
    
    url = "https://graphhopper.com/api/1/route"
    params = {
        "key": GRAPHHOPPER_API_KEY,
        "point": [f"{start_coords[0]},{start_coords[1]}", f"{end_coords[0]},{end_coords[1]}"],
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
            route = polyline.decode(data["paths"][0]["points"])
            route_cache[key] = route
            return route
        else:
            print(f"API-Fehler: {response.text}")
    except Exception as e:
        print(f"API-Verbindungsfehler: {e}")
    return []

# Dash-App initialisieren
app = dash.Dash(__name__)

# Dropdown-Optionen für die Routen
route_options = [{'label': 'Alle anzeigen', 'value': 'all'}] + [
    {'label': row['Route'], 'value': row['Route']} for _, row in df.iterrows()
]

# Auswahl für die Ansicht
view_options = [
    {'label': 'Routen-Ansicht', 'value': 'routes'},
    {'label': 'Heatmap-Analyse', 'value': 'heatmap'}
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
    dcc.RadioItems(
        id='view-selector',
        options=view_options,
        value='routes',
        labelStyle={'display': 'inline-block', 'margin': '10px'}
    ),
    html.Iframe(id="map", width="100%", height="600")
])

# Funktion zur Einfärbung der Routen basierend auf der Transporthäufigkeit
def get_route_color(transporte):
    if transporte <= 10:
        return "green"
    elif transporte <= 50:
        return "yellow"
    elif transporte <= 100:
        return "orange"
    return "red"

# Legende hinzufügen
def add_legend(m):
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; width: 250px; height: 140px;
    background-color: white; border:2px solid grey; z-index:9999; font-size:14px; box-shadow: 2px 2px 10px rgba(0,0,0,0.3); border-radius: 10px; padding: 10px; font-family: Arial, sans-serif;">
        <h4 style="margin-top: 0; text-align: center;">Transportdichte</h4>
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="width: 30px; height: 10px; background-color: #00ff00; margin-right: 10px;"></div>
            Niedrig
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="width: 30px; height: 10px; background-color: #ffff00; margin-right: 10px;"></div>
            Mittel
        </div>
        <div style="display: flex; align-items: center;">
            <div style="width: 30px; height: 10px; background-color: #ff0000; margin-right: 10px;"></div>
            Hoch
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

# Callback zum Aktualisieren der Karte
@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value'), Input('view-selector', 'value')]
)
def update_map(selected_routes, selected_view):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].tolist()

    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    if selected_view == 'routes':
        for _, row in df.iterrows():
            if row['Route'] in selected_routes:
                start_coords = row["Koordinaten Start"]
                end_coords = row["Koordinaten Ziel"]
                transporte = row["Transporte pro Woche"]
                google_maps_link = row["Routen Google Maps"]

                route_geometry = get_lkw_route(start_coords, end_coords)

                if route_geometry:
                    folium.PolyLine(
                        route_geometry,
                        color=get_route_color(transporte),
                        weight=5,
                        tooltip=f"Route: {row['Route']} - Transporte pro Woche: {transporte}"
                    ).add_to(m)

                    folium.Marker(
                        location=start_coords,
                        popup=folium.Popup(f"<b>Start</b><br><a href='{google_maps_link}' target='_blank'>Google Maps</a>", max_width=300),
                        icon=folium.Icon(color="blue")
                    ).add_to(m)

                    folium.Marker(
                        location=end_coords,
                        popup=folium.Popup(f"<b>Ziel</b><br><a href='{google_maps_link}' target='_blank'>Google Maps</a>", max_width=300),
                        icon=folium.Icon(color="red")
                    ).add_to(m)
        add_legend(m)
    else:
        heatmap_data = []
        for _, row in df.iterrows():
            if row['Route'] in selected_routes:
                start_coords = row["Koordinaten Start"]
                end_coords = row["Koordinaten Ziel"]
                transports = int(row["Transporte pro Woche"])
                route_geometry = get_lkw_route(start_coords, end_coords)

                if route_geometry:
                    heatmap_data.extend(route_geometry * transports)

        HeatMap(
            heatmap_data,
            radius=10,
            blur=15,
            max_zoom=1,
            gradient={0.2: 'green', 0.5: 'yellow', 0.8: 'red'}
        ).add_to(m)
        add_legend(m)

    try:
        map_path = "map.html"
        m.save(map_path)
        return open(map_path, "r", encoding="utf-8").read()
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Karte: {e}")
        return ""

# Server starten
if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

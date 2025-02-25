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
    else:
        heatmap_data = []
        for _, row in df.iterrows():
            if row['Route'] in selected_routes:
                start_coords = row["Koordinaten Start"]
                end_coords = row["Koordinaten Ziel"]
                transports = int(row["Transporte pro Woche"])
                route_geometry = get_lkw_route(start_coords, end_coords)

                if route_geometry:
                    valid_coords = [coord for coord in route_geometry if isinstance(coord, (list, tuple)) and len(coord) == 2]
                    heatmap_data.extend(valid_coords * transports)

        HeatMap(
            heatmap_data,
            radius=10,
            blur=15,
            max_zoom=1,
            gradient={0.2: 'green', 0.5: 'yellow', 0.8: 'red'}
        ).add_to(m)

    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

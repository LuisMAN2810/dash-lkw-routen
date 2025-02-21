import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
import requests
import json
from collections import defaultdict

# GraphHopper API-Key
GRAPHHOPPER_API_KEY = "045abf50-4e22-453a-b0a9-8374930f4e47"

# Einlesen der CSV-Datei mit den Routen
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8")

# Umwandlung der Spalte "Transporte pro Woche" in Integer
df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')

# Entferne Zeilen mit NaN-Werten in den wichtigen Spalten
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

# Bereinige die Koordinaten
df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)

# Entferne Zeilen mit fehlerhaften Koordinaten
df.dropna(subset=["Koordinaten Start", "Koordinaten Ziel"], inplace=True)

# Dash-App initialisieren
app = dash.Dash(__name__)

# Dropdown-Optionen aus der CSV-Datei laden
route_options = [{'label': 'Alle anzeigen', 'value': 'all'}] + [
    {'label': row['Route'], 'value': row['Route']} for index, row in df.iterrows()
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

# API-Abfrage für die LKW-Route
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
            return data["paths"][0]["points"]
        else:
            print(f"⚠️ Fehler bei der Routenberechnung: {response.text}")
            return None
    except Exception as e:
        print(f"⚠️ API-Fehler: {e}")
        return None

# Funktion zur Bestimmung der Routenfarbe
def get_route_color(transporte):
    if transporte <= 10:
        return "green"
    elif transporte <= 50:
        return "yellow"
    elif transporte <= 100:
        return "orange"
    else:
        return "red"

# Funktion zur Verarbeitung von überlappenden Routen
def merge_routes(route_segments):
    segment_counts = defaultdict(int)
    for segment, count in route_segments:
        segment_counts[segment] += count

    return [(segment, count) for segment, count in segment_counts.items()]

# Callback zur Aktualisierung der Karte
@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value')]
)
def update_map(selected_routes):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].tolist()

    # Erstelle eine Karte mit Fokus auf Deutschland
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    route_segments = []

    for _, row in df.iterrows():
        if row['Route'] in selected_routes:
            start_coords = row["Koordinaten Start"]
            end_coords = row["Koordinaten Ziel"]
            transporte = row["Transporte pro Woche"]
            google_maps_link = row["Routen Google Maps"]

            if start_coords and end_coords:
                route_geometry = get_lkw_route(start_coords, end_coords)
                if route_geometry:
                    route_segments.append((route_geometry, transporte))

                    # Startpunkt hinzufügen
                    folium.Marker(
                        location=[start_coords[1], start_coords[0]],
                        popup=f"<b>Startpunkt</b><br><a href='{google_maps_link}' target='_blank'>Google Maps</a>",
                        icon=folium.Icon(color="blue", icon="info-sign")
                    ).add_to(m)

                    # Zielpunkt hinzufügen
                    folium.Marker(
                        location=[end_coords[1], end_coords[0]],
                        popup=f"<b>Zielpunkt</b><br><a href='{google_maps_link}' target='_blank'>Google Maps</a>",
                        icon=folium.Icon(color="red", icon="info-sign")
                    ).add_to(m)

    # Überlappende Routenabschnitte zusammenfassen
    merged_routes = merge_routes(route_segments)

    for route_geometry, transporte in merged_routes:
        route_coords = json.loads(route_geometry)['coordinates']
        route_color = get_route_color(transporte)

        folium.PolyLine(
            locations=[[p[1], p[0]] for p in route_coords],
            color=route_color,
            weight=5,
            opacity=0.8,
            tooltip=f"Transporte: {transporte}"
        ).add_to(m)

    # Legende stabil hinzufügen
    legend_html = '''
    <div style="
        position: absolute; bottom: 20px; left: 20px; width: 200px; 
        background-color: white; border:2px solid grey; z-index:9999; 
        padding: 10px; border-radius: 10px; box-shadow: 2px 2px 10px grey;">
        <h4>Legende: Transporte pro Woche</h4>
        <p style="color:green;">0-10 Transporte</p>
        <p style="color:yellow;">10-50 Transporte</p>
        <p style="color:orange;">50-100 Transporte</p>
        <p style="color:red;">100+ Transporte</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # Karte speichern und zurückgeben
    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

# Server starten
if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

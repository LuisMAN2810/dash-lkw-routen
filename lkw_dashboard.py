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
        "geometry": True
    }

    try:
        response = requests.get(url, params=params)
        print(f"🔹 API Request sent with coordinates: {start_coords} -> {end_coords}")
        print(f"🔍 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            if response.text:
                data = response.json()
                if "paths" in data and data["paths"]:
                    return data["paths"][0]["points"]
                else:
                    print(f"⚠️ Keine Pfade in der Antwort für Koordinaten: {start_coords} -> {end_coords}")
                    return None
            else:
                print(f"⚠️ Leere Antwort von der API für Koordinaten: {start_coords} -> {end_coords}")
                return None
        else:
            print(f"❌ Fehler bei der API-Abfrage: {response.text}")
            return None
    except json.JSONDecodeError as json_error:
        print(f"🚫 JSON-Fehler beim Verarbeiten der API-Antwort: {json_error}")
        print(f"Antworttext: {response.text}")
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
        selected_routes = df['Route'].tolist()

    # Karte initialisieren
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    # Überlappende Routen-Logik
    for _, row in df.iterrows():
        if row['Route'] in selected_routes:
            start_coords = row["Koordinaten Start"]
            end_coords = row["Koordinaten Ziel"]
            transporte = row["Transporte pro Woche"]
            google_maps_link = row["Routen Google Maps"]

            if start_coords and end_coords:
                route_geometry = get_lkw_route(start_coords, end_coords)
                if route_geometry:
                    try:
                        route_coords = json.loads(route_geometry)['coordinates']
                    except json.JSONDecodeError:
                        print(f"🚫 Fehler beim Dekodieren der Route für: {route_geometry}")
                        continue
                    route_color = get_route_color(transporte)

                    # Route zeichnen
                    folium.PolyLine(
                        locations=[[p[1], p[0]] for p in route_coords],
                        color=route_color,
                        weight=5,
                        opacity=0.8,
                        tooltip=f"Transporte: {transporte}"
                    ).add_to(m)

                    # Start- und Zielpunkt hinzufügen
                    folium.Marker(
                        location=[start_coords[1], start_coords[0]],
                        popup=f"Startpunkt<br><a href='{google_maps_link}' target='_blank'>Google Maps Link</a>",
                        icon=folium.Icon(color="blue")
                    ).add_to(m)

                    folium.Marker(
                        location=[end_coords[1], end_coords[0]],
                        popup=f"Zielpunkt<br><a href='{google_maps_link}' target='_blank'>Google Maps Link</a>",
                        icon=folium.Icon(color="red")
                    ).add_to(m)

    # Legende hinzufügen
    legend_html = '''
    <div style="
        position: fixed; bottom: 20px; left: 20px; width: 200px; 
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

    # Karte speichern und anzeigen
    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

# Server starten
if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

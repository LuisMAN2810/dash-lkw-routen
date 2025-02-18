import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
import requests
import json
import polyline

# GraphHopper API-Key
GRAPHHOPPER_API_KEY = "045abf50-4e22-453a-b0a9-8374930f4e47"

# Einlesen der CSV-Datei mit den Routen
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8")

# Umwandlung der Spalte "Transporte pro Woche" in Integer
df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')

# Entferne Zeilen mit NaN-Werten in den wichtigen Spalten
df = df.dropna(subset=["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Google Maps Start", "Google Maps Ziel"])

# Funktion zur Bereinigung der Koordinaten
def clean_coordinates(coord_string):
    try:
        if isinstance(coord_string, str):
            coord_string = coord_string.replace("\t", "").replace(",", ".").strip()
            lat, lon = map(float, coord_string.split(";"))
            return [lon, lat]  # GraphHopper erwartet [LON, LAT]
    except Exception as e:
        print(f"⚠️ Fehler bei der Umwandlung der Koordinaten '{coord_string}': {e}")
    return None

# Bereinige die Koordinaten
df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)

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

# Funktion zur Berechnung der LKW-Route mit GraphHopper
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
            if "paths" in data and len(data["paths"]) > 0:
                return polyline.decode(data["paths"][0]["points"])  # Route dekodieren
        return None
    except Exception as e:
        print(f"⚠️ API-Fehler: {e}")
        return None

# Funktion zur Farbbestimmung basierend auf Transporthäufigkeit
def get_route_color(transporte):
    if transporte <= 10:
        return "green"
    elif transporte <= 50:
        return "yellow"
    elif transporte <= 100:
        return "orange"
    else:
        return "red"

@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value')]
)
def update_map(selected_routes):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].tolist()

    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    # Legende hinzufügen
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 50px; width: 180px; background-color: white; z-index:9999; padding: 10px; border-radius: 5px; border:1px solid black; font-size:14px">
        <b>Legende: Transporte pro Woche</b><br>
        <svg width="20" height="10"><line x1="0" y1="5" x2="20" y2="5" style="stroke:green;stroke-width:4"/></svg> 0 - 10<br>
        <svg width="20" height="10"><line x1="0" y1="5" x2="20" y2="5" style="stroke:yellow;stroke-width:4"/></svg> 10 - 50<br>
        <svg width="20" height="10"><line x1="0" y1="5" x2="20" y2="5" style="stroke:orange;stroke-width:4"/></svg> 50 - 100<br>
        <svg width="20" height="10"><line x1="0" y1="5" x2="20" y2="5" style="stroke:red;stroke-width:4"/></svg> 100+<br>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    segment_transports = {}

    for _, row in df.iterrows():
        if row['Route'] in selected_routes:
            start_coords = row["Koordinaten Start"]
            end_coords = row["Koordinaten Ziel"]
            transporte = row["Transporte pro Woche"]
            route_coords = get_lkw_route(start_coords, end_coords)

            if route_coords:
                for i in range(len(route_coords) - 1):
                    segment = (tuple(route_coords[i]), tuple(route_coords[i + 1]))
                    segment_transports[segment] = segment_transports.get(segment, 0) + transporte

                folium.Marker(
                    location=[start_coords[1], start_coords[0]],
                    popup=f"<b>Start:</b> <a href='{row['Google Maps Start']}' target='_blank'>Google Maps</a>",
                    icon=folium.Icon(color="blue", icon="play")
                ).add_to(m)

                folium.Marker(
                    location=[end_coords[1], end_coords[0]],
                    popup=f"<b>Ziel:</b> <a href='{row['Google Maps Ziel']}' target='_blank'>Google Maps</a>",
                    icon=folium.Icon(color="red", icon="stop")
                ).add_to(m)

    for segment, transporte in segment_transports.items():
        folium.PolyLine(
            locations=[[p[0], p[1]] for p in segment],
            color=get_route_color(transporte),
            weight=5,
            opacity=0.8,
            tooltip=f"Transporte: {transporte}"  # Tooltip zeigt die Anzahl der Transporte
        ).add_to(m)

    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

if __name__ == '__main__':
    app.run_server(debug=True)
server = app.server

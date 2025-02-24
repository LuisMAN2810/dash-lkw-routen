import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
from folium.plugins import HeatMap
import numpy as np
import requests

# GraphHopper API-Key
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

view_options = [
    {'label': 'Routen-Ansicht', 'value': 'routes'},
    {'label': 'Heatmap-Analyse', 'value': 'heatmap'}
]

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

# Funktion zur Interpolation von Koordinaten zwischen Start- und Zielpunkten
def interpolate_route(start_coords, end_coords, num_points=10):
    lat_points = np.linspace(start_coords[1], end_coords[1], num_points)
    lon_points = np.linspace(start_coords[0], end_coords[0], num_points)
    return list(zip(lat_points, lon_points))

# Legende für die Heatmap hinzufügen
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

                folium.PolyLine(
                    [start_coords, end_coords],
                    color='blue',
                    weight=5,
                    tooltip=folium.Tooltip(f"Transporte: {transporte}")
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
        # Heatmap mit interpolierten Punkten erstellen
        heatmap_data = []
        for _, row in df.iterrows():
            if row['Route'] in selected_routes:
                start_coords = row["Koordinaten Start"]
                end_coords = row["Koordinaten Ziel"]
                transports = int(row["Transporte pro Woche"])
                route_points = interpolate_route(start_coords, end_coords, num_points=20)
                heatmap_data.extend(route_points * transports)

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

if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

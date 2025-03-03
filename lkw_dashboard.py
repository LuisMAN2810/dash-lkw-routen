import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
import requests
import json
import polyline
from collections import defaultdict
import re

# OpenRouteService API-Key
ORS_API_KEY = "5b3ce3597851110001cf6248f42ededae9b5414fb25591adaff63db4"

# CSV-Datei einlesen
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8-sig")

df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')
df = df.dropna(subset=["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Routen Google Maps"])

def clean_coordinates(coord_string):
    try:
        if isinstance(coord_string, str):
            coord_string = re.sub(r'[^0-9.,\s]', '', coord_string)
            coord_string = coord_string.replace("\t", "").replace(" ", "").strip()
            coord_string = re.sub(r'\.\.', '.', coord_string)
            coord_string = coord_string.replace(";", ",")
            parts = coord_string.split(",")
            if len(parts) == 2:
                lon, lat = map(float, parts)  # Korrektur: Erst Längengrad, dann Breitengrad
                return [lon, lat]
    except Exception as e:
        print(f"⚠️ Fehler bei der Umwandlung der Koordinaten '{coord_string}': {e}")
    return None

df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)
df.dropna(subset=["Koordinaten Start", "Koordinaten Ziel"], inplace=True)

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

def get_lkw_route(start_coords, end_coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-hgv"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "coordinates": [start_coords, end_coords],
        "format": "json"
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            data = response.json()
            return polyline.decode(data["routes"][0]["geometry"])
        else:
            print(f"⚠️ API-Fehler: {response.text}")
    except Exception as e:
        print(f"⚠️ API-Verbindungsfehler: {e}")
    return None

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

@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value')]
)
def update_map(selected_routes):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].tolist()

    m = folium.Map(location=[10.4515, 51.1657] zoom_start=6)
    
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
                    tooltip=f"Transporte: {transporte}"
                ).add_to(m)
                folium.Marker(
                    location=start_coords,
                    popup=f"Startpunkt: <a href='{google_maps_link}' target='_blank'>Google Maps</a>",
                    icon=folium.Icon(color="blue")
                ).add_to(m)
                folium.Marker(
                    location=end_coords,
                    popup=f"Zielpunkt: <a href='{google_maps_link}' target='_blank'>Google Maps</a>",
                    icon=folium.Icon(color="red")
                ).add_to(m)
    
    add_legend(m)
    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

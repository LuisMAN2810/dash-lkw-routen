import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
from folium.plugins import HeatMap
import numpy as np
import requests
import polyline

GRAPHHOPPER_API_KEY = "045abf50-4e22-453a-b0a9-8374930f4e47"
route_cache = {}

file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="utf-8-sig")
df.columns = df.columns.str.strip()

if 'ï»¿Route' in df.columns:
    df = df.rename(columns={'ï»¿Route': 'Route'})

def clean_coordinates(coord_string):
    try:
        if isinstance(coord_string, str):
            coord_string = coord_string.replace("\t", "").replace(",", ".").strip()
            lat, lon = map(float, coord_string.split(";"))
            return [lat, lon]
    except:
        pass
    return None

df["Transporte pro Woche"] = pd.to_numeric(df["Transporte pro Woche"], errors='coerce')
df["Koordinaten Start"] = df["Koordinaten Start"].apply(clean_coordinates)
df["Koordinaten Ziel"] = df["Koordinaten Ziel"].apply(clean_coordinates)
df.dropna(subset=["Transporte pro Woche", "Koordinaten Start", "Koordinaten Ziel", "Routen Google Maps"], inplace=True)

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

@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value'), Input('view-selector', 'value')]
)
def update_map(selected_routes, selected_view):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].tolist()

    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    def add_legend(view):
        if view == 'routes':
            legend_html = """
                <div style='position: fixed; bottom: 50px; left: 50px; width: 250px; height: 150px;
                background-color: white; border:2px solid grey; z-index:9999; font-size:14px; padding: 10px;'>
                    <h4>Routen Transporthäufigkeit</h4>
                    <div style='margin:5px'><span style='background-color: green; width: 20px; display: inline-block;'>&nbsp;</span> 1-10 Transporte</div>
                    <div style='margin:5px'><span style='background-color: yellow; width: 20px; display: inline-block;'>&nbsp;</span> 11-50 Transporte</div>
                    <div style='margin:5px'><span style='background-color: orange; width: 20px; display: inline-block;'>&nbsp;</span> 51-100 Transporte</div>
                    <div style='margin:5px'><span style='background-color: red; width: 20px; display: inline-block;'>&nbsp;</span> Über 100 Transporte</div>
                </div>
            """
        else:
            legend_html = """
                <div style='position: fixed; bottom: 50px; left: 50px; width: 250px; height: 150px;
                background-color: white; border:2px solid grey; z-index:9999; font-size:14px; padding: 10px;'>
                    <h4>Heatmap Transportdichte</h4>
                    <div style='margin:5px'><span style='background-color: green; width: 20px; display: inline-block;'>&nbsp;</span> Niedrig</div>
                    <div style='margin:5px'><span style='background-color: yellow; width: 20px; display: inline-block;'>&nbsp;</span> Mittel</div>
                    <div style='margin:5px'><span style='background-color: red; width: 20px; display: inline-block;'>&nbsp;</span> Hoch</div>
                </div>
            """
        m.get_root().html.add_child(folium.Element(legend_html))

    if selected_view == 'routes':
        for _, row in df.iterrows():
            if row['Route'] in selected_routes:
                start_coords = row["Koordinaten Start"]
                end_coords = row["Koordinaten Ziel"]
                transporte = row["Transporte pro Woche"]
                google_maps_link = row["Routen Google Maps"]

                route_geometry = route_cache.get((tuple(start_coords), tuple(end_coords)))
                if not route_geometry:
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
                    response = requests.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        route_geometry = polyline.decode(data["paths"][0]["points"])
                        route_cache[(tuple(start_coords), tuple(end_coords))] = route_geometry
                    else:
                        continue

                folium.PolyLine(
                    route_geometry,
                    color="blue",
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
        add_legend('routes')
    else:
        heatmap_data = []
        for _, row in df.iterrows():
            if row['Route'] in selected_routes:
                start_coords = row["Koordinaten Start"]
                end_coords = row["Koordinaten Ziel"]
                transports = int(row["Transporte pro Woche"])
                route_geometry = route_cache.get((tuple(start_coords), tuple(end_coords)))
                if route_geometry:
                    valid_coords = [coord for coord in route_geometry if isinstance(coord, (list, tuple)) and len(coord) == 2]
                    heatmap_data.extend(valid_coords * transports)

        if heatmap_data:
            HeatMap(
                heatmap_data,
                radius=10,
                blur=15,
                max_zoom=1,
                gradient={0.2: 'green', 0.5: 'yellow', 0.8: 'red'}
            ).add_to(m)
        add_legend('heatmap')

    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

if __name__ == '__main__':
    app.run_server(debug=True)

server = app.server

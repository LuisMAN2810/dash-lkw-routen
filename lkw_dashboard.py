import dash
from dash import dcc, html
import pandas as pd
import folium
from dash.dependencies import Input, Output
import requests
import json
import polyline

# GraphHopper API-Key (ersetze mit deinem eigenen API-Schlüssel)
GRAPHHOPPER_API_KEY = "045abf50-4e22-453a-b0a9-8374930f4e47"

# Einlesen der Excel-Datei mit den Routen
import os

# Sicherstellen, dass die Datei aus dem aktuellen Verzeichnis geladen wird
file_path = os.path.join(BASE_DIR, "Datenblatt Routenanalyse.csv")
df = pd.read_csv(file_path, delimiter=",")  # Falls Tabulator, dann delimiter="\t"


# Funktion zur Bereinigung der Koordinaten
def clean_coordinates(coord_string):
    """ Entfernt unerwünschte Zeichen und konvertiert in Float-Koordinaten. """
    try:
        coord_string = coord_string.replace("\t", "").replace(",", ".")
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

# Dropdown-Optionen aus der Excel-Datei laden
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
    url = f"https://graphhopper.com/api/1/route?point={start_coords[1]},{start_coords[0]}&point={end_coords[1]},{end_coords[0]}&profile=truck&key={GRAPHHOPPER_API_KEY}&points_encoded=true"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "paths" in data and data["paths"]:
                encoded_polyline = data["paths"][0]["points"]
                return polyline.decode(encoded_polyline)
            else:
                print("⚠️ Keine gültigen Routenpunkte in der API-Antwort.")
                return None
        else:
            print(f"⚠️ Fehler bei der Routenberechnung: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"⚠️ API-Fehler: {e}")
        return None

# Callback zur Aktualisierung der Karte
@app.callback(
    Output('map', 'srcDoc'),
    [Input('route-selector', 'value')]
)
def update_map(selected_routes):
    if not selected_routes or 'all' in selected_routes:
        selected_routes = df['Route'].tolist()  # Alle Routen anzeigen

    # Erstelle eine Karte mit Fokus auf Deutschland
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)

    for index, row in df.iterrows():
        if row['Route'] in selected_routes:
            try:
                start_coords = row["Koordinaten Start"]
                end_coords = row["Koordinaten Ziel"]

                if start_coords and end_coords:
                    # LKW-optimierte Route abrufen
                    route_geometry = get_lkw_route(start_coords, end_coords)

                    if route_geometry:
                        folium.PolyLine(
                            locations=route_geometry,
                            color="blue",
                            weight=5,
                            opacity=0.8
                        ).add_to(m)

                    # Marker mit Infos
                    popup_text = f"Route: {row['Route']}<br>Transporte/Woche: {row['Transporte pro Woche']}<br><a href='{row['Routen Google Maps']}' target='_blank'>Google Maps Link</a>"
                    folium.Marker(start_coords[::-1], popup=popup_text, icon=folium.Icon(color="green")).add_to(m)
                    folium.Marker(end_coords[::-1], popup=popup_text, icon=folium.Icon(color="red")).add_to(m)

            except Exception as e:
                print(f"⚠️ Fehler bei Route {row['Route']}: {e}")

    # Karte speichern und anzeigen
    map_path = "map.html"
    m.save(map_path)
    return open(map_path, "r", encoding="utf-8").read()

# Server starten
if __name__ == '__main__':
    app.run_server(debug=True)


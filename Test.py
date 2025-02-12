import openrouteservice

ORS_API_KEY = "5b3ce3597851110001cf6248f42ededae9b5414fb25591adaff63db4"  # Ersetze mit deinem API-Key
client = openrouteservice.Client(key=ORS_API_KEY)

try:
    # Test-Request für eine Route
    route = client.directions(
        coordinates=[(11.5667, 48.2167), (10.3333, 52.1500)],  # München -> Salzgitter
        profile='driving-hgv',
        format='geojson'
    )
    print("API funktioniert! ✅")
except Exception as e:
    print(f"⚠️ API-Fehler: {e}")

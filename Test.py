import pandas as pd

# CSV-Datei einlesen
file_path = "Datenblatt Routenanalyse .csv"
df = pd.read_csv(file_path, delimiter=";", encoding="ISO-8859-1")

# Spaltennamen und erste Zeilen ausgeben
print("Spaltennamen:")
print(df.columns)

print("\nErste Zeilen der Daten:")
print(df.head())

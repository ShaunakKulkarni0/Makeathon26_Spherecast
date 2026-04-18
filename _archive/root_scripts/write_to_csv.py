import sqlite3
import csv
from pathlib import Path

def export_database_to_csv(db_path: str, output_csv: str):
    # Verbindung zur Datenbank herstellen
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Erlaubt Zugriff auf Spalten per Name
    cursor = conn.cursor()

    try:
        # Alle Daten aus der Supplier-Tabelle abrufen
        cursor.execute("SELECT * FROM Supplier")
        rows = cursor.fetchall()

        if not rows:
            print("Die Datenbank ist leer. Es gibt nichts zu exportieren.")
            return

        # Spaltennamen aus den Metadaten extrahieren
        column_names = rows[0].keys()

        # CSV-Datei schreiben
        with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=column_names)
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))

        print(f"Erfolg! {len(rows)} Zeilen wurden in '{output_csv}' geschrieben.")

    except sqlite3.OperationalError as e:
        print(f"Fehler: Die Tabelle 'Supplier' wurde nicht gefunden ({e}).")
    finally:
        conn.close()

# Pfad zu deiner db.sqlite (anpassen, falls sie in einem anderen Ordner liegt)
db_file = "db.sqlite" 
csv_file = "suppliers.csv"

if __name__ == "__main__":
    export_database_to_csv(db_file, csv_file)
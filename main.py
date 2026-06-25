import os
import json
from modules import fetcher
from modules import analyzer
from modules import reporter

def main():
    print("=" * 60)
    print("Phaidra Metadata Auditor - Pipeline gestartet")
    print("=" * 60)

    # 1. PFADE DEFINIEREN (Absolut, basierend auf dem Speicherort dieser main.py)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROFILES_PATH = os.path.join(BASE_DIR, "config", "profiles.json")
    OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "Output", "audit_report.csv")

    # 2. KONFIGURATION ZENTRAL LADEN (Variante A)
    try:
        with open(PROFILES_PATH, "r", encoding="utf-8") as f:
            profiles = json.load(f)
        print(f"[SUCCESS] Konfiguration erfolgreich geladen aus: {PROFILES_PATH}")
    except FileNotFoundError:
        print(f"[CRITICAL ERROR] 'profiles.json' wurde nicht gefunden unter: {PROFILES_PATH}")
        print("Abbruch der Pipeline.")
        return
    except json.JSONDecodeError as e:
        print(f"[CRITICAL ERROR] Syntaxfehler in der 'profiles.json': {e}")
        print("Abbruch der Pipeline.")
        return

    # 3. DATA FETCHING (Rohdaten von Phaidra holen)
    print("\n[INFO] Starte Datenabruf via Fetcher...")
    try:
        # HINWEIS: Passe die Argumente an die tatsächliche fetcher-Funktion an 
        # (z.B. wenn eine Collection-ID oder eine Liste von PIDs übergeben wird)
        raw_objects = fetcher.harvest_oer_data() 
        print(f"[SUCCESS] {len(raw_objects)} Objekte erfolgreich abgerufen.")
    except Exception as e:
        print(f"[CRITICAL ERROR] Fehler beim Datenabruf: {e}")
        return

    # 4. DATA ANALYSIS (Verarbeitung mit injizierter Konfiguration)
    print("\n[INFO] Starte Metadaten-Analyse und Format-Mapping...")
    compliance_records = []
    
    for idx, item in enumerate(raw_objects, start=1):
        try:
            # Hier reichen wird die 'profiles' zentral in den Analyzer weitergeleitet
            record = analyzer.analyze_uploader_metadata(item, profiles)
            compliance_records.append(record)
        except Exception as e:
            # Verhindert, dass ein einzelnes defektes Objekt die gesamte Pipeline crasht
            pid = item.get("@id", f"Unbekannt (Index {idx})")
            print(f"[WARNUNG] Objekt {pid} konnte nicht analysiert werden: {e}")

    print(f"[SUCCESS] Analyse abgeschlossen. {len(compliance_records)} Datensätze verarbeitet.")

    # 5. REPORTING (Ergebnisse in CSV schreiben)
    print("\n[INFO] Generiere CSV-Report...")
    try:
        reporter.generate_csv_report(compliance_records, OUTPUT_CSV_PATH)
        print(f"[SUCCESS] Report erfolgreich gespeichert unter: {OUTPUT_CSV_PATH}")
    except Exception as e:
        print(f"[CRITICAL ERROR] Erstellung des Reports fehlgeschlagen: {e}")
        return

    print("\n" + "=" * 60)
    print("Auditor-Pipeline erfolgreich beendet.")
    print("=" * 60)

if __name__ == "__main__":
    main()
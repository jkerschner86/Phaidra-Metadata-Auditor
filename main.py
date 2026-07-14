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

# 3. DATA FETCHING (Interaktive Parameter-Abfrage)
    print("\n[INFO] Konfiguration des Datenabrufs")
    
    # 1. Abfrage: Objekt-Typ (Was?)
    while True:
        type_input = input("Welcher Objekt-Typ soll analysiert werden? (Aktuell verfügbar: 1 = OER): ").strip()
        if type_input == "1":
            target_scope = "oer"
            break
        else:
            print("[Hinweis] Zukünftige Module (wie RD) sind noch nicht implementiert. Bitte '1' für OER wählen.")

    # 2. Abfrage: Zeitraum (Wann?)
    while True:
        year_input = input("Für welchen Zeitraum soll der Audit laufen? (Jahreszahl ab 2014 ODER 'alle' für den gesamten Zeitraum): ").strip().lower()
        
        if year_input in ["alle", "all"]:
            target_year = "ALL"
            break
        else:
            try:
                target_year = int(year_input)
                if target_year >= 2014:
                    break
                else:
                    print("Das Jahr muss mindestens 2014 sein.")
            except ValueError:
                print("Bitte eine gültige Jahreszahl oder das Wort 'alle' eingeben.")

    print("\n[INFO] Starte Datenabruf via Fetcher...")
    try:
        raw_objects = fetcher.harvest_oer_data(scope=target_scope, year=target_year) 
        print(f"[SUCCESS] {len(raw_objects)} Objekte erfolgreich abgerufen.")
    except Exception as e:
        print(f"[CRITICAL ERROR] Fehler beim Datenabruf: {e}")
        return

# 4. DATA ANALYSIS (Verarbeitung mit injizierter Konfiguration)
    print("\n[INFO] Starte Metadaten-Analyse und Format-Mapping...")
    compliance_records = []
    
    for idx, item in enumerate(raw_objects, start=1):
        try:
            # ARCHITEKTUR-FIX: Prüfen, ob die Daten im Wrapper liegen, und sauber entpacken
            if isinstance(item, dict) and "metadata" in item:
                metadata_content = item["metadata"]
                api_date = item.get("api_date", "Unknown")
                pid = item.get("_harvester_pid", f"Index_{idx}")
            else:
                # Fallback für alte Datenstrukturen
                metadata_content = item
                api_date = "Unknown"
                pid = item.get("@id", f"Unbekannt (Index {idx})") if isinstance(item, dict) else f"Unbekannt (Index {idx})"

            # Das reine JSON-LD an den Analyzer übergeben
            record = analyzer.analyze_uploader_metadata(metadata_content, profiles)
            
            record["object_id"] = pid

            # Das OAI-Datum direkt in den Datensatz injizieren (ersetzt "Pending API Update")
            record["date_published"] = api_date

            # Das Jahr sicher extrahieren (nimmt die ersten 4 Zeichen vor dem Bindestrich)
            record["year_published"] = api_date.split("-")[0] if api_date and api_date != "Unknown" else "Unknown"
            
            compliance_records.append(record)
            
        except Exception as e:
            # Verhindert, dass ein einzelnes defektes Objekt die gesamte Pipeline crasht
            print(f"[WARNUNG] Objekt konnte nicht analysiert werden: {e}")

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
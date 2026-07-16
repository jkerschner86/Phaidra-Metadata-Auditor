import os
import json
from datetime import datetime
from modules import fetcher
from modules import analyzer
from modules import reporter
from modules import visualizer

def main():
    print("=" * 60)
    print("Phaidra Metadata Auditor - Pipeline gestartet")
    print("=" * 60)

    # 1. PFADE DEFINIEREN
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RULES_PATH = os.path.join(BASE_DIR, "config", "audit_rules.json")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "Output", f"audit_report_{timestamp}.csv")
    OUTPUT_PNG_PATH = os.path.join(BASE_DIR, "Output", f"dashboard_{timestamp}.png")

    # 2. REGELWERK LADEN & PROFIL WÄHLEN
    try:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            all_rules = json.load(f)
    except Exception as e:
        print(f"[CRITICAL ERROR] Konnte audit_rules.json nicht laden: {e}")
        return

    print("\nVerfügbare Audit-Profile:")
    print("1: Open Educational Resources (OER)")
    print("2: Research Data (Forschungsdaten)")
    
    choice = input("Bitte Profilnummer wählen (1 oder 2): ").strip()
    if choice == "2":
        active_profile_key = "research_data"
    else:
        active_profile_key = "oer"
        
    active_rules = all_rules[active_profile_key]
    print(f"\n[INFO] Aktives Profil: {active_rules['name']}")

# 3. DATA FETCHING
    print("\n[INFO] Konfiguration des Datenabrufs")
    year_choice = input("Für welchen Zeitraum soll der Audit laufen? (Jahreszahl ab 2014 ODER 'alle'): ").strip()
    
    print("\n[INFO] Starte Datenabruf via Fetcher...")
    
    # Der Scope wird nun 100% dynamisch aus der Profil-Wahl (JSON) abgeleitet
    raw_objects = fetcher.harvest_oer_data(active_profile_key, year_choice)
    

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

            # Das reine JSON-LD und das aktive Regelwerk an den Analyzer übergeben
            record = analyzer.analyze_uploader_metadata(metadata_content, active_rules)
            
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
    print("\n[INFO] Generiere visuelles Dashboard...")
    try:
        # Wir übergeben nun zusätzlich den Profilnamen und die Jahreswahl
        visualizer.generate_dashboard(
            compliance_records, 
            OUTPUT_PNG_PATH, 
            active_rules["name"], 
            year_choice
        )
        print(f"[SUCCESS] Dashboard erfolgreich gespeichert unter: {OUTPUT_PNG_PATH}")
    except Exception as e:
        print(f"[ERROR] Erstellung des Dashboards fehlgeschlagen: {e}")

    print("\n" + "=" * 60)
    print("Auditor-Pipeline erfolgreich beendet.")
    print("=" * 60)

if __name__ == "__main__":
    main()
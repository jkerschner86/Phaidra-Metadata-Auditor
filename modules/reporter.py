"""
=============================================================================
MODULE: reporter.py (Semicolon CSV Engine & Stats Summary)
PURPOSE: Outputs compliance statistics with automated key-mapping (DictWriter).
=============================================================================
"""
import csv
import os
from typing import List, Dict, Any

def generate_summary_stats(compliance_records: List[Dict[str, Any]]) -> None:
    """Erzeugt eine übersichtliche Konsolenausgabe der Audit-Statistiken (Ampel-Verteilung)."""
    total = len(compliance_records)
    if total == 0:
        print("\n[Fehler] Keine Datensätze für eine Statistik vorhanden.")
        return

    stats = {"RED": 0, "GREEN": 0, "GOLD": 0}
    
    for record in compliance_records:
        status = record.get("status", "RED")
        if status in stats:
            stats[status] += 1

    print("\n" + "=" * 50)
    print("         METADATEN-AUDIT ZUSAMMENFASSUNG")
    print("=" * 50)
    print(f"Analysierte Objekte gesamt: {total}")
    print(f"🔴 ROT (Nicht erfüllt):          {stats['RED']} ({stats['RED']/total*100:.1f}%)")
    print(f"🟢 GRÜN (Erfüllt):               {stats['GREEN']} ({stats['GREEN']/total*100:.1f}%)")
    print(f"🟡 GOLD (LOD / GND vorhanden):   {stats['GOLD']} ({stats['GOLD']/total*100:.1f}%)")
    print("=" * 50 + "\n")


def generate_csv_report(compliance_records: List[Dict[str, Any]], output_filepath: str) -> str:
    """Generiert einen semikolierten CSV-Report mittels automatisiertem DictWriter."""
    if not compliance_records:
        print("[Warnung] Keine Datensätze zum Schreiben vorhanden.")
        return output_filepath

    # Definieren die exakten Keys aus dem Analyzer. DictWriter nutzt dies als Spaltenordnung.
    headers = [
        "object_id", "title", "status", "visibility", "gold_indicators_found", 
        "missing_fields", "oefos_ids", "oefos_labels", "bk_ids", "bk_labels", 
        "gnd_ids", "gnd_labels", "mime_types", "file_formats",
        "date_published", "year_published", "language", "object_types", "doi_internal", "doi_external"
    ]

    # Verzeichnis erstellen, falls es noch nicht existiert (z.B. nach frischem Klonen)
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    try:
        with open(output_filepath, mode="w", newline="", encoding="utf-8-sig") as csv_file:
            # Verwendung von DictWriter eliminiert positionelle Fehler
            writer = csv.DictWriter(csv_file, fieldnames=headers, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Header schreiben
            writer.writeheader()

            for record in compliance_records:
                # Vorverarbeitung: Listen plattklopfen und fehlende Keys abfangen
                processed_row = {}
                for field in headers:
                    val = record.get(field)
                    if isinstance(val, list):
                        processed_row[field] = ", ".join(str(x) for x in val) if val else "None"
                    elif val is None:
                        processed_row[field] = "None"
                    else:
                        processed_row[field] = str(val)

                writer.writerow(processed_row)

        print(f"[Erfolg] CSV-Report generiert unter: {output_filepath}")
        return output_filepath
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Fehler beim Schreiben der CSV-Datei: {e}")
        raise e
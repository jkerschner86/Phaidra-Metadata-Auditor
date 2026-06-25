"""
=============================================================================
MODULE: reporter.py (Semicolon CSV Engine & Stats Summary)
PURPOSE: Outputs compliance statistics with clear comma separation inside cells.
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
    print(f"Analysierte OER-Objekte gesamt: {total}")
    print(f"🔴 ROT (Nicht erfüllt):          {stats['RED']} ({stats['RED']/total*100:.1f}%)")
    print(f"🟢 GRÜN (Erfüllt):               {stats['GREEN']} ({stats['GREEN']/total*100:.1f}%)")
    print(f"🟡 GOLD (Übererfüllt / LOD):     {stats['GOLD']} ({stats['GOLD']/total*100:.1f}%)")
    print("=" * 50 + "\n")

def generate_csv_report(compliance_records: List[Dict[str, Any]], output_filepath: str = "Output/audit_report.csv") -> str:
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    # "file_formats" ganz am Ende ergänzt
    headers = [
        "object_id", "status", "visibility", "gold_indicators_found", 
        "missing_fields", "oefos_ids", "oefos_labels", "bk_ids", 
        "bk_labels", "gnd_ids", "gnd_labels", "mime_types", "file_formats"
    ]

    try:
        with open(output_filepath, mode="w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)

            for record in compliance_records:
                def list_to_cell(val):
                    if isinstance(val, list):
                        return ", ".join(str(x) for x in val)
                    return str(val) if val is not None else "None"

                writer.writerow([
                    # ... [Alle bisherigen Spalten von object_id bis mime_types] ...
                    record.get("object_id"),
                    record.get("status"),
                    record.get("visibility"),
                    record.get("gold_indicators_found"),
                    list_to_cell(record.get("missing_fields")),
                    list_to_cell(record.get("oefos_ids")),
                    list_to_cell(record.get("oefos_labels")),
                    list_to_cell(record.get("bk_ids")),
                    list_to_cell(record.get("bk_labels")),
                    list_to_cell(record.get("gnd_ids")),
                    list_to_cell(record.get("gnd_labels")),
                    list_to_cell(record.get("mime_types")),
                    list_to_cell(record.get("file_formats")) # NEU hinzugefügt
                ])
        print(f"[Erfolg] CSV-Report generiert unter: {output_filepath}")
        return output_filepath
    except Exception as e:
        print(f"[Fehler] CSV-Erstellung fehlgeschlagen: {e}")
        return ""
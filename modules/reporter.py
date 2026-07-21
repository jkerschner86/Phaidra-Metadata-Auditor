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
    """Generates a clear console output of the audit statistics (traffic light distribution)."""
    total = len(compliance_records)
    if total == 0:
        print("\n[Error] No records available for statistics.")
        return

    stats = {"RED": 0, "GREEN": 0, "GOLD": 0}
    
    for record in compliance_records:
        status = record.get("status", "RED")
        if status in stats:
            stats[status] += 1

    print("\n" + "=" * 50)
    print("         METADATA AUDIT SUMMARY")
    print("=" * 50)
    print(f"Total objects analyzed: {total}")
    print(f"🔴 RED (Not fulfilled):          {stats['RED']} ({stats['RED']/total*100:.1f}%)")
    print(f"🟢 GREEN (Fulfilled):            {stats['GREEN']} ({stats['GREEN']/total*100:.1f}%)")
    print(f"🟡 GOLD (LOD / GND present):     {stats['GOLD']} ({stats['GOLD']/total*100:.1f}%)")
    print("=" * 50 + "\n")


def generate_csv_report(compliance_records: List[Dict[str, Any]], output_filepath: str) -> str:
    """Generates a semicolon-separated CSV report using an automated DictWriter."""
    if not compliance_records:
        print("[Warning] No records available to write.")
        return output_filepath

    # Define the exact keys from the analyzer. DictWriter uses this for column ordering.
    headers = [
        "object_id", "title", "status", "visibility", "gold_indicators_found", 
        "missing_fields", "orcid","ror","oefos_ids", "oefos_labels", "bk_ids", "bk_labels", 
        "gnd_ids", "gnd_labels", "mime_types", "file_formats",
        "date_published", "year_published", "language", "object_types", "doi_internal", "doi_external"
    ]

    # Create directory if it doesn't exist yet (e.g., after a fresh clone)
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    try:
        with open(output_filepath, mode="w", newline="", encoding="utf-8-sig") as csv_file:
            # Using DictWriter eliminates positional errors
            writer = csv.DictWriter(csv_file, fieldnames=headers, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Write header
            writer.writeheader()

            for record in compliance_records:
                # Preprocessing: flatten lists and catch missing keys
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

        print(f"[Success] CSV report generated at: {output_filepath}")
        return output_filepath
        
    except Exception as e:
        print(f"[CRITICAL ERROR] Error writing the CSV file: {e}")
        raise e
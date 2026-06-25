import os
import json
from modules.fetcher import harvest_oer_data
from modules.analyzer import execute_compliance_audit
from modules.reporter import generate_csv_report, generate_summary_stats

if __name__ == "__main__":
    print("=" * 70)
    print("   PHAIDRA PIPELINE - RUNTIME ENVIRONMENT")
    print("=" * 70)
    
    with open('profiles.json', 'r', encoding='utf-8') as config_file:
        oer_profile = json.load(config_file)["oerhub_austria"]

    # Führt ab sofort immer den Live-Call durch
    raw_memory_bucket = harvest_oer_data(
        classification_id=oer_profile["classification_id"]
    )

    if not raw_memory_bucket:
        print("\nAbbruch: Keine Daten zur Analyse geliefert.")
        exit(0)

    print("\nExecuting Advanced Graph Traversal & Entity Label Matching...")
    audited_compliance_records = execute_compliance_audit(raw_memory_bucket, oer_profile)

    generate_summary_stats(audited_compliance_records)
    generate_csv_report(audited_compliance_records)
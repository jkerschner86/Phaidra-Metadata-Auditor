import os
import json
from datetime import datetime
from modules import fetcher
from modules import analyzer
from modules import reporter
from modules import visualizer

def main():
    print("=" * 60)
    print("Phaidra Metadata Auditor - Pipeline started")
    print("=" * 60)

    # 1. DEFINE PATHS
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RULES_PATH = os.path.join(BASE_DIR, "config", "audit_rules.json")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "Output", f"audit_report_{timestamp}.csv")
    OUTPUT_PNG_PATH = os.path.join(BASE_DIR, "Output", f"dashboard_{timestamp}.png")

    # 2. LOAD RULES & SELECT PROFILE
    try:
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            all_rules = json.load(f)
    except Exception as e:
        print(f"[CRITICAL ERROR] Could not load audit_rules.json: {e}")
        return

    print("\nAvailable Audit Profiles:")
    print("1: Open Educational Resources (OER)")
    print("2: Research Data")
    
    choice = input("Please select a profile number (1 or 2): ").strip()
    if choice == "2":
        active_profile_key = "research_data"
    else:
        active_profile_key = "oer"
        
    active_rules = all_rules[active_profile_key]
    print(f"\n[INFO] Active profile: {active_rules['name']}")

# 3. DATA FETCHING
    print("\n[INFO] Data fetch configuration")
    year_choice = input("For which period should the audit run? (Year from 2014 OR 'all'): ").strip()
    
    print("\n[INFO] Starting data fetch via Fetcher...")
    
    # The scope is now derived 100% dynamically from the profile choice (JSON)
    raw_objects = fetcher.harvest_oer_data(active_profile_key, year_choice)
    

# 4. DATA ANALYSIS (Processing with injected configuration)
    print("\n[INFO] Starting metadata analysis and format mapping...")
    compliance_records = []
    
    for idx, item in enumerate(raw_objects, start=1):
        try:
            # ARCHITECTURE FIX: Check if the data is in the wrapper and unpack cleanly
            if isinstance(item, dict) and "metadata" in item:
                metadata_content = item["metadata"]
                api_date = item.get("api_date", "Unknown")
                pid = item.get("_harvester_pid", f"Index_{idx}")
            else:
                # Fallback for old data structures
                metadata_content = item
                api_date = "Unknown"
                pid = item.get("@id", f"Unknown (Index {idx})") if isinstance(item, dict) else f"Unknown (Index {idx})"

            # Pass the pure JSON-LD and the active rule set to the analyzer
            record = analyzer.analyze_uploader_metadata(metadata_content, active_rules)
            
            record["object_id"] = pid

            # Inject the OAI date directly into the record (replaces "Pending API Update")
            record["date_published"] = api_date

            # Safely extract the year (takes the first 4 characters before the hyphen)
            record["year_published"] = api_date.split("-")[0] if api_date and api_date != "Unknown" else "Unknown"
            
            compliance_records.append(record)
            
        except Exception as e:
            # Prevents a single broken object from crashing the entire pipeline
            print(f"[WARNING] Object could not be analyzed: {e}")

    print(f"[SUCCESS] Analysis complete. {len(compliance_records)} records processed.")


    reporter.generate_summary_stats(compliance_records)

    # 5. REPORTING (Write results to CSV)
    print("\n[INFO] Generating CSV report...")
    try:
        reporter.generate_csv_report(compliance_records, OUTPUT_CSV_PATH)
        print(f"[SUCCESS] Report successfully saved to: {OUTPUT_CSV_PATH}")
    except Exception as e:
        print(f"[CRITICAL ERROR] Report creation failed: {e}")
        return
    print("\n[INFO] Generating visual dashboard...")
    try:
        # We now additionally pass the profile name and the year choice
        visualizer.generate_dashboard(
            compliance_records, 
            OUTPUT_PNG_PATH, 
            active_rules["name"], 
            year_choice
        )
        print(f"[SUCCESS] Dashboard successfully saved to: {OUTPUT_PNG_PATH}")
    except Exception as e:
        print(f"[ERROR] Dashboard creation failed: {e}")

    print("\n" + "=" * 60)
    print("Auditor pipeline finished successfully.")
    print("=" * 60)

if __name__ == "__main__":
    main()
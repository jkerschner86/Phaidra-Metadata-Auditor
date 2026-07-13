"""
=============================================================================
MODULE: analyzer.py (Uploader Compliance Engine)
PURPOSE: Evaluates data entry quality (Red/Green/Gold) based on field presence.
=============================================================================
"""

import json
import os
from typing import List, Dict, Any

# Dynamisches Laden der externen JSON-Konfiguration
MIME_MAPPING = {}
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    json_path = os.path.join(project_root, "config", "mime_mapping.json")
    
    with open(json_path, "r", encoding="utf-8") as f:
        MIME_MAPPING = json.load(f)
    print("[Erfolg] Konfiguration 'mime_mapping.json' erfolgreich geladen.") 
except Exception as e:
    print("\n" + "!"*50)
    print(f"[CRITICAL ERROR] MAPPING-DATEI KONNTE NICHT GELADEN WERDEN!")
    print(f"Pfad: {json_path if 'json_path' in locals() else 'Unbekannt'}")
    print(f"Details: {e}")
    print("!"*50 + "\n")

# Hilfsfunktion für DOIs (muss über analyze_uploader_metadata stehen)
def extract_all_dois(obj: Any) -> List[str]:
    dois = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            dois.extend(extract_all_dois(v))
    elif isinstance(obj, list):
        for item in obj:
            dois.extend(extract_all_dois(item))
    elif isinstance(obj, str):
        if "doi.org/" in obj:
            dois.append(obj)
    return dois

# profiles wird nun als optionales Argument hineingereicht
# Die Signatur bleibt unangetastet! Kein 'api_date' Parameter hier.
def analyze_uploader_metadata(data: Dict[str, Any], profiles: Dict[str, Any] = None) -> Dict[str, Any]:
    pid = data.get("_harvester_pid")
    if not pid:
        raw_id = data.get("@id", "")
        pid = "o:" + raw_id.split("/o:")[-1] if "/o:" in raw_id else "Unknown PID"

    missing_fields = []
    
    # --- BESTEHENDE LOGIK ---
    # Titel
    title_list = data.get("dce:title", [])
    has_title = False
    title = "Kein Titel"
    language = "Unknown" # NEU: Sprache via Titel-Heuristik
    
    if title_list and "bf:mainTitle" in title_list[0]:
        main_title_obj = title_list[0]["bf:mainTitle"]
        if isinstance(main_title_obj, list) and len(main_title_obj) > 0:
            title = main_title_obj[0].get("@value", "")
            language = main_title_obj[0].get("@language", "Unknown") # Sprache abgreifen
            if title.strip():
                has_title = True
    if not has_title:
        missing_fields.append("TITLE")

    # Lizenz
    rights = data.get("edm:rights", [])
    license_url = rights[0] if rights else ""
    has_valid_license = "creativecommons.org" in license_url or "spdx.org" in license_url
    if not has_valid_license:
        missing_fields.append("LICENSE_URL")

    # LOD / Disziplinen
    gnd_ids, gnd_labels = [], []
    oefos_ids, oefos_labels = [], []
    bk_ids, bk_labels = [], []
    subjects = data.get("dcterms:subject", [])
    for sub in subjects:
        exact_matches = sub.get("skos:exactMatch", [])
        pref_labels = sub.get("skos:prefLabel", [])
        label_val = pref_labels[0].get("@value", "None") if pref_labels else "None"
        for match in exact_matches:
            if "d-nb.info/gnd/" in match:
                gnd_ids.append(match.split("/gnd/")[-1])
                gnd_labels.append(label_val)
            elif "oefos2012:" in match:
                oefos_ids.append(match)
                oefos_labels.append(label_val)
            elif "uri.gbv.de/terminology/bk/" in match:
                bk_ids.append(match.split("/bk/")[-1])
                bk_labels.append(label_val)

    has_discipline = bool(oefos_ids or bk_ids)
    if not has_discipline:
        missing_fields.append("MISSING_DISCIPLINE")

    # Formate
    raw_mimes = data.get("ebucore:hasMimeType", [])
    mime_types, file_formats = [], [] 
    for mime in raw_mimes:
        val = mime if isinstance(mime, str) else mime.get("@value") if isinstance(mime, dict) else None
        if val:
            mime_types.append(val)
            clean_name = MIME_MAPPING.get(val, val.split("/")[-1].upper() if "/" in val else "Unknown")
            if clean_name not in file_formats:
                file_formats.append(clean_name)

    # --- NEUE LOGIK ---
    # Objekt Typen
    object_types = []
    for obj_type in data.get("edm:hasType", []):
        labels = obj_type.get("skos:prefLabel", [])
        if labels and isinstance(labels, list):
            val = labels[0].get("@value")
            if val and val not in object_types:
                object_types.append(val)

    # DOIs
    all_dois = list(set(extract_all_dois(data)))
    internal_dois = [d for d in all_dois if "10.60522" in d]
    external_dois = [d for d in all_dois if "10.60522" not in d]

    # Status
    if not has_title or not has_valid_license or not has_discipline:
        status, visibility = "RED", False
    elif len(gnd_ids) > 0:
        status, visibility = "GOLD", True
    else:
        status, visibility = "GREEN", True

    return {
        "object_id": pid,
        "title": title,
        "status": status,
        "visibility": visibility,
        "gold_indicators_found": len(gnd_ids),
        "missing_fields": missing_fields if missing_fields else ["None"],
        "oefos_ids": oefos_ids,
        "oefos_labels": oefos_labels,
        "bk_ids": bk_ids,
        "bk_labels": bk_labels,
        "gnd_ids": gnd_ids,
        "gnd_labels": gnd_labels,
        "mime_types": mime_types if mime_types else ["Unknown"],
        "file_formats": file_formats if file_formats else ["Unknown"],
        # Die 5 neuen Felder integriert:
        "date_published": "Pending API Update", # Platzhalter für den späteren Fetcher-Umbau
        "language": language,
        "object_types": object_types if object_types else ["Unknown"],
        "doi_internal": internal_dois[0] if internal_dois else "None",
        "doi_external": external_dois if external_dois else ["None"]
    }


# Reicht profiles an analyze_uploader_metadata weiter
def run_audit(raw_records: List[Dict[str, Any]], profiles: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    return [analyze_uploader_metadata(rec, profiles) for rec in raw_records]


# Parameter-Name vereinheitlicht (profiles) und an die Einzelanalyse durchgereicht
def execute_compliance_audit(raw_records: List[Dict[str, Any]], profiles: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Iteriert über alle JSON-LD Datensätze des Uploaders mit injizierter Konfiguration."""
    print(f"Starte Metadaten-Audit für {len(raw_records)} Objekte...")
    audit_results = []
    
    for record in raw_records:
        try:
            # profiles wird hier explizit übergeben
            analyzed = analyze_uploader_metadata(record, profiles)
            audit_results.append(analyzed)
        except Exception as e:
            print(f"[Warnung] Fehler bei der Analyse eines Objekts: {e}")
            continue
            
    return audit_results
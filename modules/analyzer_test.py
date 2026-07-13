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


# profiles wird nun als optionales Argument hineingereicht
def analyze_uploader_metadata(data: Dict[str, Any], profiles: Dict[str, Any] = None) -> Dict[str, Any]:
    """Analysiert die Feldinformationen eines Objekts auf das Ampelsystem."""
    
    # Hole die PID direkt aus der Harvester-Injektion
    pid = data.get("_harvester_pid")
    
    # Fallback, falls das Skript mal isoliert mit Rohdaten getestet wird
    if not pid:
        raw_id = data.get("@id", "")
        pid = "o:" + raw_id.split("/o:")[-1] if "/o:" in raw_id else "Unknown PID"

    # HINWEIS FÜR DIE ZUKUNFT:
    # Hier kann später auf profiles zugegriffen werden, z.B.:
    # oer_requirements = profiles.get("oer_hub", {}) if profiles else {}

    # 2. Feldprüfungen (Uploader-Eingaben)
    missing_fields = []
    
    # Titel prüfen
    title_list = data.get("dce:title", [])
    has_title = False
    title = "Kein Titel"
    if title_list and "bf:mainTitle" in title_list[0]:
        main_title_obj = title_list[0]["bf:mainTitle"]
        if isinstance(main_title_obj, list) and len(main_title_obj) > 0:
            title = main_title_obj[0].get("@value", "")
            if title.strip():
                has_title = True
    if not has_title:
        missing_fields.append("TITLE")

    # Lizenz prüfen
    rights = data.get("edm:rights", [])
    license_url = rights[0] if rights else ""
    # Einfache Validierung gegen spdx/creative commons URLs
    has_valid_license = "creativecommons.org" in license_url or "spdx.org" in license_url
    if not has_valid_license:
        missing_fields.append("LICENSE_URL")

    # Klassifikationen & Normdaten sammeln (LOD Kriterium)
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

    # Hat der Uploader überhaupt eine Fachdisziplin hinterlegt?
    has_discipline = bool(oefos_ids or bk_ids)
    if not has_discipline:
        missing_fields.append("MISSING_DISCIPLINE")

    # EXTRAKTION UND MAPPING DER DATENFORMATE
    raw_mimes = data.get("ebucore:hasMimeType", [])
    mime_types = []
    file_formats = [] 

    for mime in raw_mimes:
        val = None
        if isinstance(mime, str):
            val = mime
        elif isinstance(mime, dict) and "@value" in mime:
            val = mime["@value"]
                
        if val:
            mime_types.append(val)
            clean_name = MIME_MAPPING.get(val, val.split("/")[-1].upper() if "/" in val else "Unknown")
            if clean_name not in file_formats:
                file_formats.append(clean_name)

    # 3. Ampel-Logik (Status-Zuweisung)
    if not has_title or not has_valid_license or not has_discipline:
        status = "RED"
        visibility = False
    elif len(gnd_ids) > 0:
        status = "GOLD"
        visibility = True
    else:
        status = "GREEN"
        visibility = True

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
        "file_formats": file_formats if file_formats else ["Unknown"]
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
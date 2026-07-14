"""
=============================================================================
MODULE: analyzer.py (Compliance Engine)
PURPOSE: Evaluates data entry quality (Red/Green/Gold) handling Phaidra's bf:note schemas.
=============================================================================
"""

import json
import os
import re
from typing import List, Dict, Any

MIME_MAPPING = {}
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    json_path = os.path.join(project_root, "config", "mime_mapping.json")
    with open(json_path, "r", encoding="utf-8") as f:
        MIME_MAPPING = json.load(f)
except Exception:
    pass

def extract_all_dois(obj: Any) -> List[str]:
    """Durchsucht rekursiv den gesamten Baum nach dem DOI-Muster (10.XXXX/YYYY)."""
    dois = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            dois.extend(extract_all_dois(v))
    elif isinstance(obj, list):
        for item in obj:
            dois.extend(extract_all_dois(item))
    elif isinstance(obj, str):
        # Regex filtert exakt die DOI heraus, unabhängig von Prefix oder URL-Struktur
        match = re.search(r'(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)', obj)
        if match:
            dois.append(match.group(1))
    return dois

def get_phaidra_node(data: Dict[str, Any]) -> Dict[str, Any]:
    """Findet den eigentlichen Metadaten-Knoten im @graph Array."""
    # Wir fügen bf:note als Suchkriterium hinzu!
    keys_to_check = ["dce:title", "dcterms:title", "bf:note", "edm:hasType"]
    
    if any(k in data for k in keys_to_check):
        return data
        
    if "@graph" in data and isinstance(data["@graph"], list):
        for node in data["@graph"]:
            if isinstance(node, dict) and any(k in node for k in keys_to_check):
                return node
                
        # Fallback auf o:ID im Graph
        for node in data["@graph"]:
            if isinstance(node, dict) and "@id" in node and "o:" in str(node["@id"]):
                return node
    return data

def analyze_uploader_metadata(data: Dict[str, Any], profiles: Dict[str, Any] = None) -> Dict[str, Any]:
    # ---------------------------------------------------------
    # 1. PID ZUVERLÄSSIG EXTRAHIEREN (Deine funktionierende Original-Logik)
    # ---------------------------------------------------------
    pid = data.get("_harvester_pid")
    if not pid:
        raw_id = data.get("@id", "")
        if "/o:" in raw_id:
            pid = "o:" + raw_id.split("/o:")[-1]
        elif raw_id.startswith("o:"):
            pid = raw_id
        else:
            pid = "Unknown PID"

    # 2. Jetzt erst den Node-Knoten für die Metadaten-Analyse isolieren
    node = get_phaidra_node(data)
    missing_fields = []

    # ---------------------------------------------------------
    # 2. TITEL
    # ---------------------------------------------------------
    title_list = node.get("dce:title", node.get("dcterms:title", []))
    has_title = False
    title_valid = False
    title = "Kein Titel"
    language = "Unknown"
    
    if title_list:
        first_title = title_list[0] if isinstance(title_list, list) else title_list
        if isinstance(first_title, dict):
            if "bf:mainTitle" in first_title:
                main_title_obj = first_title["bf:mainTitle"]
                if isinstance(main_title_obj, list) and len(main_title_obj) > 0:
                    title_raw = main_title_obj[0].get("@value", "")
                    language = main_title_obj[0].get("@language", "Unknown")
                    if title_raw and title_raw.strip():
                        title = title_raw.strip()
                        title_valid = True
            elif "@value" in first_title:
                title_raw = first_title.get("@value", "")
                language = first_title.get("@language", "Unknown")
                if title_raw and title_raw.strip():
                    title = title_raw.strip()
                    title_valid = True
        elif isinstance(first_title, str) and first_title.strip():
            title = first_title.strip()
            title_valid = True

    if not title_valid:
        missing_fields.append("TITLE_MISSING")

    # ---------------------------------------------------------
    # 3. DESCRIPTION (Inkl. Sanity Check und bf:note Support)
    # ---------------------------------------------------------
    desc_valid = False
    has_desc = False
    desc_texts = []

    # A) Standard-Felder
    for key in ["dce:description", "dcterms:description", "bf:summary"]:
        val = node.get(key)
        if val:
            v_list = val if isinstance(val, list) else [val]
            for item in v_list:
                if isinstance(item, dict):
                    desc_texts.append(item.get("@value", ""))
                else:
                    desc_texts.append(str(item))

    # B) Fallback: bf:note (Deine Entdeckung implementiert)
    if not desc_texts:
        notes = node.get("bf:note", [])
        notes = notes if isinstance(notes, list) else [notes]
        for note in notes:
            if isinstance(note, dict):
                labels = note.get("skos:prefLabel", [])
                labels = labels if isinstance(labels, list) else [labels]
                for label in labels:
                    if isinstance(label, dict) and "@value" in label:
                        desc_texts.append(label["@value"])

    # C) Validierung auf Länge (Mindestens 15 Zeichen)
    for text in desc_texts:
        if text and text.strip():
            has_desc = True
            if len(text.strip()) >= 15:
                desc_valid = True
                break

    if not has_desc:
        missing_fields.append("DESCRIPTION_MISSING")
    elif not desc_valid:
        missing_fields.append("DESCRIPTION_INSUFFICIENT_LENGTH")

    # ---------------------------------------------------------
    # 4. LICENSE
    # ---------------------------------------------------------
    rights_list = node.get("edm:rights", node.get("dcterms:rights", []))
    license_url = ""
    if rights_list:
        first_right = rights_list[0] if isinstance(rights_list, list) else rights_list
        if isinstance(first_right, dict):
            license_url = first_right.get("@id", first_right.get("@value", ""))
        else:
            license_url = str(first_right)

    has_valid_license = "creativecommons.org" in license_url or "spdx.org" in license_url
    if not has_valid_license:
        missing_fields.append("LICENSE_URL_MISSING_OR_INVALID")

    # ---------------------------------------------------------
    # 5. SUBJECTS & DISZIPLINEN
    # ---------------------------------------------------------
    subjects = node.get("dcterms:subject", node.get("dc:subject", []))
    subjects = subjects if isinstance(subjects, list) else [subjects]
    
    gnd_ids, gnd_labels = [], []
    oefos_ids, oefos_labels = [], []
    bk_ids, bk_labels = [], []
    
    for sub in subjects:
        if not isinstance(sub, dict): continue
        exact_matches = sub.get("skos:exactMatch", sub.get("exactMatch", []))
        exact_matches = exact_matches if isinstance(exact_matches, list) else [exact_matches]
        
        pref_labels = sub.get("skos:prefLabel", sub.get("prefLabel", []))
        pref_labels = pref_labels if isinstance(pref_labels, list) else [pref_labels]
        
        label_val = "None"
        if pref_labels:
            if isinstance(pref_labels[0], dict):
                label_val = pref_labels[0].get("@value", "None")
            else:
                label_val = str(pref_labels[0])
                
        for match in exact_matches:
            if isinstance(match, dict): match = match.get("@id", match.get("@value", ""))
            if not isinstance(match, str): continue
            
            if "d-nb.info/gnd/" in match:
                gnd_ids.append(match.split("/gnd/")[-1])
                gnd_labels.append(label_val)
            
            elif "oefos2012:" in match:
                oefos_ids.append(match)
                oefos_labels.append(label_val)
            
            elif "uri.gbv.de/terminology/bk/" in match:
                bk_id = match.split("/bk/")[-1]
                bk_ids.append(bk_id)
                
                # NEU: ID am Anfang des Labels wegschneiden (inkl. Leerzeichen)
                clean_label = label_val
                if clean_label.startswith(bk_id):
                    clean_label = clean_label[len(bk_id):].strip()
                bk_labels.append(clean_label)

    has_discipline = bool(oefos_ids or bk_ids)
    if not has_discipline:
        missing_fields.append("MISSING_DISCIPLINE")

    # ---------------------------------------------------------
    # 6. FORMATS
    # ---------------------------------------------------------
    raw_mimes = node.get("ebucore:hasMimeType", node.get("hasMimeType", []))
    raw_mimes = raw_mimes if isinstance(raw_mimes, list) else [raw_mimes]
    mime_types, file_formats = [], []
    for mime in raw_mimes:
        val = mime if isinstance(mime, str) else mime.get("@value") if isinstance(mime, dict) else None
        if val:
            mime_types.append(val)
            clean_name = MIME_MAPPING.get(val, val.split("/")[-1].upper() if "/" in val else "Unknown")
            if clean_name not in file_formats:
                file_formats.append(clean_name)

    # ---------------------------------------------------------
    # 7. TYPES
    # ---------------------------------------------------------
    raw_types = node.get("edm:hasType", node.get("hasType", []))
    raw_types = raw_types if isinstance(raw_types, list) else [raw_types]
    object_types = []
    for obj_type in raw_types:
        if isinstance(obj_type, dict):
            labels = obj_type.get("skos:prefLabel", obj_type.get("prefLabel", []))
            labels = labels if isinstance(labels, list) else [labels]
            if labels and isinstance(labels[0], dict):
                val = labels[0].get("@value")
                if val and val not in object_types:
                    object_types.append(val)

# ---------------------------------------------------------
    # 8. DOIs
    # ---------------------------------------------------------
    # WICHTIG: Suche im gesamten 'data' Graphen, nicht nur im isolierten 'node'!
    all_dois = list(set(extract_all_dois(data)))
    
    # Wir formatieren sie für das CSV direkt als saubere URLs
    internal_dois = [f"https://doi.org/{d}" for d in all_dois if "10.60522" in d]
    external_dois = [f"https://doi.org/{d}" for d in all_dois if "10.60522" not in d]

    # ---------------------------------------------------------
    # 9. AMPEL
    # ---------------------------------------------------------
    if not title_valid or not desc_valid or not has_valid_license or not has_discipline:
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
        "language": language,
        "object_types": object_types if object_types else ["Unknown"],
        "doi_internal": internal_dois[0] if internal_dois else "None",
        "doi_external": external_dois if external_dois else ["None"]
    }

def run_audit(raw_records: List[Dict[str, Any]], profiles: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    return [analyze_uploader_metadata(rec, profiles) for rec in raw_records]

def execute_compliance_audit(raw_records: List[Dict[str, Any]], profiles: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    print(f"Starte Analyse für {len(raw_records)} Objekte...")
    audit_results = []
    for record in raw_records:
        try:
            analyzed = analyze_uploader_metadata(record, profiles)
            audit_results.append(analyzed)
        except Exception as e:
            print(f"[Warnung] Fehler bei der Analyse eines Objekts: {e}")
            continue
    return audit_results
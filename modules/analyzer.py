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

def extract_identifiers(obj: Any) -> Dict[str, List[str]]:
    """Recursively searches the tree for ORCIDs and RORs (DOIs have their own dual-system)."""
    found = {"orcid": [], "ror": []}
    
    def _scan(node):
        if isinstance(node, dict):
            for v in node.values():
                _scan(v)
        elif isinstance(node, list):
            for item in node:
                _scan(item)
        elif isinstance(node, str):
            # ORCID Filter (Format: XXXX-XXXX-XXXX-XXXX)
            orcid_match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', node)
            if orcid_match: 
                found["orcid"].append(orcid_match.group(1))
            
            # ROR Filter (Format: ror.org/XXXXXXXXX)
            ror_match = re.search(r'(ror\.org/[a-zA-Z0-9]+)', node)
            if ror_match: 
                found["ror"].append("https://" + ror_match.group(1))
                
    _scan(obj)
    return found

def get_phaidra_node(data: Dict[str, Any]) -> Dict[str, Any]:
    """Finds the actual metadata node within the @graph array."""
    # We add bf:note as a search criterion!
    keys_to_check = ["dce:title", "dcterms:title", "bf:note", "edm:hasType"]
    
    if any(k in data for k in keys_to_check):
        return data
        
    if "@graph" in data and isinstance(data["@graph"], list):
        for node in data["@graph"]:
            if isinstance(node, dict) and any(k in node for k in keys_to_check):
                return node
                
        # Fallback to o:ID in the graph
        for node in data["@graph"]:
            if isinstance(node, dict) and "@id" in node and "o:" in str(node["@id"]):
                return node
    return data

def analyze_uploader_metadata(data: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    
    # ---------------------------------------------------------
    # NEW: LOAD DYNAMIC VOCABULARIES FROM PROFILE
    # ---------------------------------------------------------
    vocabularies = rules.get("allowed_vocabularies", {})
    allowed_disciplines = vocabularies.get("discipline_prefixes", ["oefos2012:", "uri.gbv.de/terminology/bk/"])
    allowed_licenses = vocabularies.get("license_domains", ["creativecommons.org", "spdx.org"])
    gnd_prefixes = vocabularies.get("gnd_prefix", ["d-nb.info/gnd/"])

    # ---------------------------------------------------------
    # 1. RELIABLY EXTRACT PID
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

    node = get_phaidra_node(data)
    missing_fields = []

    # ---------------------------------------------------------
    # 2. TITLE
    # ---------------------------------------------------------
    title_list = node.get("dce:title", node.get("dcterms:title", []))
    has_title = False
    title_valid = False
    title = "No Title"
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
    # 3. DESCRIPTION
    # ---------------------------------------------------------
    desc_valid = False
    has_desc = False
    desc_texts = []

    for key in ["dce:description", "dcterms:description", "bf:summary"]:
        val = node.get(key)
        if val:
            v_list = val if isinstance(val, list) else [val]
            for item in v_list:
                if isinstance(item, dict):
                    desc_texts.append(item.get("@value", ""))
                else:
                    desc_texts.append(str(item))

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
    # 4. LICENSE (Dynamic)
    # ---------------------------------------------------------
    rights_list = node.get("edm:rights", node.get("dcterms:rights", []))
    license_url = ""
    if rights_list:
        first_right = rights_list[0] if isinstance(rights_list, list) else rights_list
        if isinstance(first_right, dict):
            license_url = first_right.get("@id", first_right.get("@value", ""))
        else:
            license_url = str(first_right)

    # Dynamically checks against the list of allowed domains from the JSON
    has_valid_license = any(domain in license_url for domain in allowed_licenses)
    if not has_valid_license:
        missing_fields.append("LICENSE_URL_MISSING_OR_INVALID")

    # ---------------------------------------------------------
    # 5. SUBJECTS & DISCIPLINES (Dynamic)
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
            
            # Dynamic GND check
            if any(gnd_pref in match for gnd_pref in gnd_prefixes):
                for gnd_pref in gnd_prefixes:
                    if gnd_pref in match:
                        gnd_ids.append(match.split(gnd_pref)[-1])
                        gnd_labels.append(label_val)
                        break
            
            # Dynamic discipline check
            elif any(disc_pref in match for disc_pref in allowed_disciplines):
                for disc_pref in allowed_disciplines:
                    if disc_pref in match:
                        # Separation for backward-compatible CSV export
                        if "bk/" in disc_pref or "bk" in disc_pref.lower():
                            bk_id = match.split(disc_pref)[-1]
                            bk_ids.append(bk_id)
                            clean_label = label_val
                            if clean_label.startswith(bk_id):
                                clean_label = clean_label[len(bk_id):].strip()
                            bk_labels.append(clean_label)
                        else:
                            # By default, queue into the primary discipline list (ÖFOS/Container)
                            oefos_ids.append(match)
                            oefos_labels.append(label_val)
                        break

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
    # 8. IDENTIFIERS - DUAL SYSTEM FOR DOIs, ORCID & ROR
    # ---------------------------------------------------------
    
    # --- A) DOI ---
    all_dois = []
    rda_ids = node.get("rdam:P30004", data.get("rdam:P30004", []))
    rda_ids = rda_ids if isinstance(rda_ids, list) else [rda_ids]

    for ident in rda_ids:
        if isinstance(ident, dict) and ident.get("@type") == "ids:doi":
            val = ident.get("@value")
            if val:
                all_dois.append(val)

    if not all_dois:
        def _scan_dois(obj):
            found = []
            if isinstance(obj, dict):
                for v in obj.values(): found.extend(_scan_dois(v))
            elif isinstance(obj, list):
                for item in obj: found.extend(_scan_dois(item))
            elif isinstance(obj, str):
                match = re.search(r'(10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+)', obj)
                if match: found.append(match.group(1))
            return found

        fallback_dois = _scan_dois(data)
        if fallback_dois:
            all_dois.extend(fallback_dois)
            missing_fields.append("DOI_STRUCTURALLY_MISPLACED")

    # --- B & C) ORCID & ROR ---
    strict_orcids = []
    strict_rors = []

    for key, val_list in node.items():
        if key.startswith("role:") or key in ["dc:creator", "dc:contributor", "schema:author"]:
            if not isinstance(val_list, list): 
                val_list = [val_list]
            
            for item in val_list:
                if not isinstance(item, dict): continue
                
                matches = item.get("skos:exactMatch", item.get("exactMatch", []))
                matches = matches if isinstance(matches, list) else [matches]
                for match in matches:
                    m_val = match if isinstance(match, str) else match.get("@value", match.get("@id", ""))
                    
                    o_match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', str(m_val))
                    if o_match: strict_orcids.append(o_match.group(1))
                        
                    r_match = re.search(r'(ror\.org/[a-zA-Z0-9]+)', str(m_val))
                    if r_match: strict_rors.append("https://" + r_match.group(1))

                affiliations = item.get("schema:affiliation", [])
                affiliations = affiliations if isinstance(affiliations, list) else [affiliations]
                for affil in affiliations:
                    if not isinstance(affil, dict): continue
                    
                    affil_matches = affil.get("skos:exactMatch", affil.get("exactMatch", []))
                    affil_matches = affil_matches if isinstance(affil_matches, list) else [affil_matches]
                    for a_match in affil_matches:
                        a_val = a_match if isinstance(a_match, str) else a_match.get("@id", a_match.get("@value", ""))
                        r_match = re.search(r'(ror\.org/[a-zA-Z0-9]+)', str(a_val))
                        if r_match: strict_rors.append("https://" + r_match.group(1))

    if not strict_orcids:
        def _scan_orcids(obj):
            found = []
            if isinstance(obj, dict):
                for v in obj.values(): found.extend(_scan_orcids(v))
            elif isinstance(obj, list):
                for item in obj: found.extend(_scan_orcids(item))
            elif isinstance(obj, str):
                match = re.search(r'(\d{4}-\d{4}-\d{4}-\d{3}[0-9X])', obj)
                if match: found.append(match.group(1))
            return found

        fallback_orcids = _scan_orcids(data)
        if fallback_orcids:
            strict_orcids.extend(fallback_orcids)
            missing_fields.append("ORCID_STRUCTURALLY_MISPLACED")

    if not strict_rors:
        def _scan_rors(obj):
            found = []
            if isinstance(obj, dict):
                for v in obj.values(): found.extend(_scan_rors(v))
            elif isinstance(obj, list):
                for item in obj: found.extend(_scan_rors(item))
            elif isinstance(obj, str):
                match = re.search(r'(ror\.org/[a-zA-Z0-9]+)', obj)
                if match: found.append("https://" + match.group(1))
            return found

        fallback_rors = _scan_rors(data)
        if fallback_rors:
            strict_rors.extend(fallback_rors)
            missing_fields.append("ROR_STRUCTURALLY_MISPLACED")

    # --- D) Clean up ---
    all_dois = list(set(all_dois))
    orcid = list(set(strict_orcids))
    ror = list(set(strict_rors))
    
    internal_dois = [f"https://doi.org/{d}" for d in all_dois if "10.60522" in d]
    external_dois = [f"https://doi.org/{d}" for d in all_dois if "10.60522" not in d]

    # ---------------------------------------------------------
    # 9. TRAFFIC LIGHT & EVALUATION (Dynamic via audit_rules.json)
    # ---------------------------------------------------------
    status = "GREEN"
    visibility = True
    
    mandatory = rules.get("mandatory_fields", [])
    
    if "title" in mandatory and not title_valid:
        status, visibility = "RED", False
    if "description" in mandatory and not desc_valid:
        status, visibility = "RED", False
    if "license" in mandatory and not has_valid_license:
        status, visibility = "RED", False
    if "discipline" in mandatory and not has_discipline:
        status, visibility = "RED", False
    if "orcid" in mandatory and not orcid:
        status, visibility = "RED", False
        if "MISSING_ORCID" not in missing_fields: missing_fields.append("MISSING_ORCID")
    if "doi_internal" in mandatory and not internal_dois:
        status, visibility = "RED", False
        if "MISSING_INTERNAL_DOI" not in missing_fields: missing_fields.append("MISSING_INTERNAL_DOI")

    gold_count = 0
    gold_indicators_list = rules.get("gold_indicators", [])
    
    if "gnd" in gold_indicators_list:
        gold_count += len(gnd_ids)
    if "ror" in gold_indicators_list:
        gold_count += len(ror)
    if "orcid" in gold_indicators_list:
        gold_count += len(orcid)

    if status != "RED" and gold_count > 0:
        status = "GOLD"

    return {
        "object_id": pid,
        "title": title,
        "status": status,
        "visibility": visibility,
        "gold_indicators_found": gold_count,
        "missing_fields": missing_fields if missing_fields else ["None"],
        "oefos_ids": oefos_ids,
        "oefos_labels": oefos_labels,
        "bk_ids": bk_ids,
        "bk_labels": bk_labels,
        "gnd_ids": gnd_ids,
        "gnd_labels": gnd_labels,
        "orcid": orcid if orcid else ["None"],
        "ror": ror if ror else ["None"],
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
    print(f"Starting analysis for {len(raw_records)} objects...")
    audit_results = []
    for record in raw_records:
        try:
            analyzed = analyze_uploader_metadata(record, profiles)
            audit_results.append(analyzed)
        except Exception as e:
            print(f"[Warning] Error analyzing an object: {e}")
            continue
    return audit_results
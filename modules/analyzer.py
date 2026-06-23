"""
=============================================================================
MODULE: analyzer.py (Uploader Compliance Engine)
PURPOSE: Evaluates data entry quality (Red/Green/Gold) based on field presence.
=============================================================================
"""
from typing import List, Dict, Any

def analyze_uploader_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analysiert die Feldinformationen eines Objekts auf das Ampelsystem."""
    
    # ARCHITEKTUR-FIX: Hole die PID direkt aus der Harvester-Injektion
    pid = data.get("_harvester_pid")
    
    # Fallback, falls das Skript mal isoliert mit Rohdaten getestet wird
    if not pid:
        raw_id = data.get("@id", "")
        pid = "o:" + raw_id.split("/o:")[-1] if "/o:" in raw_id else "Unknown PID"

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

    # 3. Ampel-Logik (Status-Zuweisung)
    # ROT: Kritische Pflichtfelder fehlen komplett
    if not has_title or not has_valid_license or not has_discipline:
        status = "RED"
        visibility = False
    # GOLD: Pflichtfelder erfüllt + Übererfüllung durch Normdaten/LOD (GND vorhanden)
    elif len(gnd_ids) > 0:
        status = "GOLD"
        visibility = True
    # GRÜN: Pflichtfelder erfüllt, aber keine zusätzliche LOD-Anreicherung (keine GNDs)
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
        "gnd_labels": gnd_labels
    }

def run_audit(raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [analyze_uploader_metadata(rec) for rec in raw_records]

def execute_compliance_audit(raw_records: List[Dict[str, Any]], profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Iteriert über alle JSON-LD Datensätze des Uploaders.
    Akzeptiert das 'profile' Argument, um die Kompatibilität mit main.py zu wahren.
    """
    print(f"Starte Metadaten-Audit für {len(raw_records)} Objekte...")
    audit_results = []
    
    for record in raw_records:
        try:
            analyzed = analyze_uploader_metadata(record)
            audit_results.append(analyzed)
        except Exception as e:
            print(f"[Warnung] Fehler bei der Analyse eines Objekts: {e}")
            continue
            
    return audit_results
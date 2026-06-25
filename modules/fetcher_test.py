"""
=============================================================================
MODULE: fetcher.py (OAI ID-Locator & JSON-LD Harvester)
PURPOSE: Extracts PIDs from the OER set and fetches the uploader's raw JSON-LD.
=============================================================================
"""
import json
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

PHAIDRA_BASE_URL = "https://phaidra.ustp.at"
OAI_ENDPOINT = f"{PHAIDRA_BASE_URL}/api/oai"
MAX_WORKERS = 10

def fetch_single_jsonld(pid: str) -> Optional[Dict[str, Any]]:
    """Holt den JSON-LD Graphen direkt aus dem Objekt-Kern."""
    url = f"{PHAIDRA_BASE_URL}/api/object/{pid}/jsonld"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None

def harvest_pids_from_set(set_name: str = "oer") -> List[str]:
    """Nutzt OAI-PMH ListIdentifiers, um alle PIDs des OER-Sets zu sammeln."""
    params = {
        "verb": "ListIdentifiers",
        "metadataPrefix": "oai_dc",  # oai_dc reicht hier, da wir nur die Header-PIDs wollen
        "set": set_name
    }
    try:
        response = requests.get(OAI_ENDPOINT, params=params, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        namespaces = {'oai': 'http://www.openarchives.org/OAI/2.0/'}
        
        pids = []
        for identifier_tag in root.findall('.//oai:identifier', namespaces):
            raw_id = identifier_tag.text
            if raw_id and ":o:" in raw_id:
                pids.append("o:" + raw_id.split(":o:")[-1])
        return pids
    except Exception as e:
        print(f"[Fehler] Konnte PIDs aus Set '{set_name}' nicht lesen: {e}")
        return []

def harvest_oer_data(set_name: str = "oer", classification_id: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
    """Sammelt JSON-LD Datensätze und protokolliert fehlgeschlagene Downloads."""
    target_set = set_name
    if classification_id and classification_id != "YA8R-1M0D":
        target_set = classification_id

    pids = harvest_pids_from_set(target_set)
    if not pids:
        return []

    print(f"-> {len(pids)} Objekte im Set '{target_set}' lokalisiert. Starte Download...")
    
    jsonld_results = []
    failed_pids = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_pid = {executor.submit(fetch_single_jsonld, pid): pid for pid in pids}
        for future in as_completed(future_to_pid):
            pid = future_to_pid[future]
            try:
                data = future.result()
                if data:
                    jsonld_results.append(data)
                else:
                    failed_pids.append(pid)
            except Exception:
                failed_pids.append(pid)

    # Kritische Lücke schließen: Fehlermeldung im Terminal ausgeben
    if failed_pids:
        print(f"\n[Warnung] {len(failed_pids)} Objekte konnten nicht geladen werden (Timeout/404/403):")
        print(f"          Betroffene PIDs: {', '.join(failed_pids)}\n")

    return jsonld_results
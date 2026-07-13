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
    """
    Sammelt alle JSON-LD Datensätze des OER-Sets.
    Akzeptiert 'classification_id' und flexible Keyword-Argumente (**kwargs),
    um Abstürze mit einer unveränderten main.py zu verhindern.
    """
    # Bestimme das Ziel-Set. Wenn nichts übergeben wird, greift der Standard 'oer'
    target_set = set_name
    
    # Falls in der main.py das oer_profile['classification_id'] den Wert 'oer' enthält,
    # nutzen wir diesen als Set-Namen.
    if classification_id and classification_id != "YA8R-1M0D":
        target_set = classification_id

    pids = harvest_pids_from_set(target_set)
    if not pids:
        return []

    print(f"-> {len(pids)} Objekte im Set '{target_set}' lokalisiert. Starte Download...")
    jsonld_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_pid = {executor.submit(fetch_single_jsonld, pid): pid for pid in pids}
        for future in as_completed(future_to_pid):
            data = future.result()
            if data:
                jsonld_results.append(data)
    return jsonld_results
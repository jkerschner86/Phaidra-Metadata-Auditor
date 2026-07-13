"""
=============================================================================
MODULE: fetcher.py (OAI ID-Locator & JSON-LD Harvester)
PURPOSE: Extracts PIDs, handles OAI pagination, filters by year/all, and packages API dates.
=============================================================================
"""
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

PHAIDRA_BASE_URL = "https://phaidra.ustp.at"
OAI_ENDPOINT = f"{PHAIDRA_BASE_URL}/api/oai"
MAX_WORKERS = 10

def fetch_single_jsonld(pid: str, api_date: str) -> Optional[Dict[str, Any]]:
    """Holt den JSON-LD Graphen und verpackt ihn mit dem API-Datum."""
    url = f"{PHAIDRA_BASE_URL}/api/object/{pid}/jsonld"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "metadata": data,
            "api_date": api_date,
            "_harvester_pid": pid
        }
    except requests.RequestException:
        return None

def harvest_pids_from_oai(scope: str, year: Union[int, str]) -> Dict[str, str]:
    """
    Nutzt OAI-PMH ListIdentifiers inkl. ResumptionTokens.
    Akzeptiert ein spezifisches Jahr oder 'ALL' für den gesamten Zeitraum ab 2014.
    """
    params = {
        "verb": "ListIdentifiers",
        "metadataPrefix": "oai_dc"
    }

    # Datums-Logik dynamisch aufbauen
    if str(year).upper() == "ALL":
        # Ab 2014 bis heute (kein 'until' Parameter nötig)
        params["from"] = "2014-01-01T00:00:00Z"
        print(f"[Fetcher] Frage PIDs ab (Scope: {scope}, Gesamter Zeitraum ab 2014)...")
    else:
        if int(year) < 2014:
            print("[Fehler] Das Jahr muss >= 2014 sein. Breche ab.")
            return {}
        # Spezifisches Jahr eingrenzen
        params["from"] = f"{year}-01-01T00:00:00Z"
        params["until"] = f"{year}-12-31T23:59:59Z"
        print(f"[Fetcher] Frage PIDs ab (Scope: {scope}, Jahr: {year})...")

    # Set filtern
    if scope != "entire_repo":
        params["set"] = scope

    namespaces = {'oai': 'http://www.openarchives.org/OAI/2.0/'}
    pids_with_dates = {}
    
    while True:
        try:
            response = requests.get(OAI_ENDPOINT, params=params, timeout=15)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            
            # PIDs und Datestamps extrahieren
            for header in root.findall('.//oai:header', namespaces):
                if header.get('status') == 'deleted':
                    continue
                    
                identifier_tag = header.find('oai:identifier', namespaces)
                datestamp_tag = header.find('oai:datestamp', namespaces)
                
                if identifier_tag is not None and ":o:" in identifier_tag.text:
                    raw_id = identifier_tag.text
                    pid = "o:" + raw_id.split(":o:")[-1]
                    date_val = datestamp_tag.text.split("T")[0] if datestamp_tag is not None else "Unknown"
                    pids_with_dates[pid] = date_val

            # Paginierung prüfen (ResumptionToken)
            token_tag = root.find('.//oai:resumptionToken', namespaces)
            if token_tag is not None and token_tag.text:
                params = {"verb": "ListIdentifiers", "resumptionToken": token_tag.text}
                print(f"[Fetcher] Lade nächste Seite... (Bisher gefunden: {len(pids_with_dates)})")
            else:
                break 

        except Exception as e:
            print(f"[Fehler] Abbruch bei der OAI-Abfrage: {e}")
            break

    return pids_with_dates


def harvest_oer_data(scope: str = "oer", year: Union[int, str] = "ALL") -> List[Dict[str, Any]]:
    """Sammelt JSON-LD Datensätze basierend auf den gefundenen PIDs parallel ein."""
    
    # HIER war der Variablen-Fehler (scope statt set_name)
    pids_dict = harvest_pids_from_oai(scope, year)
    if not pids_dict:
        return []

    print(f"-> {len(pids_dict)} Objekte lokalisiert. Starte parallelen Download...")
    
    jsonld_results = []
    failed_pids = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_pid = {
            executor.submit(fetch_single_jsonld, pid, date): pid 
            for pid, date in pids_dict.items()
        }
        
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

    if failed_pids:
        print(f"\n[Warnung] {len(failed_pids)} Objekte konnten nicht geladen werden (Timeout/404):")
        print(f"          {', '.join(failed_pids[:10])} ... (und weitere)\n")

    return jsonld_results
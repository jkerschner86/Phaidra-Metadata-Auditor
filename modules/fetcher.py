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

PHAIDRA_BASE_URL = "https://phaidra.ustp.at"  # oder austauschbar je nach Instanz
OAI_ENDPOINT = f"{PHAIDRA_BASE_URL}/api/oai"
MAX_WORKERS = 10

# NEW: Standard browser headers to bypass firewall/WAF blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/xml, text/xml, */*"
}

def fetch_single_jsonld(pid: str, api_date: str) -> Optional[Dict[str, Any]]:
    """Retrieves the JSON-LD graph and packages it with the API date."""
    url = f"{PHAIDRA_BASE_URL}/api/object/{pid}/jsonld"
    try:
        # Pass headers to bypass blocks
        response = requests.get(url, headers=HEADERS, timeout=10)
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
    Utilizes OAI-PMH ListIdentifiers including ResumptionTokens.
    Accepts a specific year or 'ALL'/'ALLE' for the entire period starting from 2014.
    """
    params = {
        "verb": "ListIdentifiers",
        "metadataPrefix": "oai_dc"
    }

    year_str = str(year).strip().upper()
    if year_str in ["ALL", "ALLE"]:
        params["from"] = "2014-01-01T00:00:00Z"
        print(f"[Fetcher] Requesting PIDs (Scope: {scope}, Entire period from 2014)...")
    else:
        if not str(year).strip().isdigit() or int(year) < 2014:
            print(f"[Error] Invalid year: '{year}'. Please enter 'all' or a number from 2014 onwards.")
            return {}
        params["from"] = f"{year}-01-01T00:00:00Z"
        params["until"] = f"{year}-12-31T23:59:59Z"
        print(f"[Fetcher] Requesting PIDs (Scope: {scope}, Year: {year})...")

    if scope != "entire_repo":
        params["set"] = scope

    namespaces = {'oai': 'http://www.openarchives.org/OAI/2.0/'}
    pids_with_dates = {}
    
    while True:
        try:
            # Pass headers to bypass blocks
            response = requests.get(OAI_ENDPOINT, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
            
            # NEW: Defensive Pre-Check. Verify if the response is actually XML before parsing.
            content_start = response.content.strip()[:20].decode('utf-8', errors='ignore').lower()
            if not content_start.startswith("<?xml") and not content_start.startswith("<oai-pmh"):
                print(f"[Error] Server returned non-XML format (likely a firewall block page).")
                print(f"        Preview: {response.content[:150]}...")
                break

            root = ET.fromstring(response.content)
            
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

            token_tag = root.find('.//oai:resumptionToken', namespaces)
            if token_tag is not None and token_tag.text:
                params = {"verb": "ListIdentifiers", "resumptionToken": token_tag.text}
                print(f"[Fetcher] Loading next page... (Found so far: {len(pids_with_dates)})")
            else:
                break 

        except Exception as e:
            print(f"[Error] Aborted during OAI request: {e}")
            break

    return pids_with_dates

def harvest_oer_data(scope: str = "oer", year: Union[int, str] = "ALL") -> List[Dict[str, Any]]:
    """Collects JSON-LD datasets in parallel based on the located PIDs."""
    
    pids_dict = harvest_pids_from_oai(scope, year)
    if not pids_dict:
        return []

    print(f"-> {len(pids_dict)} objects located. Starting parallel download...")
    
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
        print(f"\n[Warning] {len(failed_pids)} objects could not be loaded (Timeout/404):")
        print(f"          {', '.join(failed_pids[:10])} ... (and more)\n")

    return jsonld_results
# PMA - Phaidra Compliance Pipeline (v1.0.0) Initial Release

## Overview
The PMA is a modular, Python-based data stewardship tool designed to automate compliance checks for Phaidra repository instances. It fetches repository data via API, evaluates it against a configuration-driven rule set, and generates actionable CSV reports and visual dashboards.

## Features
*   **Hybrid Fetching Engine:** Uses OAI-PMH for initial set indexing and the REST API for high-resolution JSON-LD extraction.
*   **Traffic Light Compliance:**
    *   🔴 **RED:** Missing mandatory fields (e.g., Title, License).
    *   🟢 **GREEN:** Structurally sound and hub-compliant.
    *   🟡 **GOLD:** Enhanced with Linked Open Data (LOD) identifiers (ORCID, ROR, GND).
*   **Configuration-Driven:** Adapts to different repository requirements via `audit_rules.json` without code changes.
*   **Visual Analytics:** Generates a 3x3 dashboard (.png) to track longitudinal metadata quality.

## Prerequisites
*   Python 3.9+
*   Dependencies listed in `requirements.txt`

## Installation
1. Clone this repository or download the source code.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration
Before running the pipeline, ensure your local settings are correct:
1.  **Endpoint:** Update `PHAIDRA_BASE_URL` in `modules/fetcher.py` to match your institutional API.
2.  **Rules:** Define mandatory fields, allowed vocabularies, and gold indicators in `config/audit_rules.json`.
3.  **Scope:** Adjust the OAI set scope parameter depending on how the local repository manager configured the target collections.

## Usage
Run the orchestrator script from your terminal:
```bash
python main.py
```
The CLI will prompt you for:
1.  The audit profile (e.g., OER or Research Data).
2.  The temporal scope (a specific year from 2014 onwards, or 'all').

## Output
The pipeline generates two files in the `Output/` directory, automatically timestamped to prevent overwriting:
*   `audit_report_[timestamp].csv`: A detailed, semicolon-separated table mapping the compliance status of each object.
*   `dashboard_[timestamp].png`: A high-resolution analytical dashboard.

## Architecture
*   `main.py`: Central orchestrator.
*   `modules/fetcher.py`: Handles OAI-PMH indexing and asynchronous JSON-LD payload retrieval.
*   `modules/analyzer.py`: Executes the "Role-First" compliance evaluation.
*   `modules/reporter.py`: Serializes dictionaries into flattened CSV reports.
*   `modules/visualizer.py`: Aggregates data and plots the management dashboard.

phaidra-auditor/
├── 📁 config/                 # Configuration files
│   ├── 📄 mime_mapping.json   # File format definitions
│   └── 📄 audit_rules.json    # Validation rules & profile definitions
├── 📁 modules/                # Core pipeline logic
│   ├── 🐍 analyzer.py         # Traffic Light compliance engine
│   ├── 🐍 fetcher.py          # OAI-PMH & REST API data retrieval
│   ├── 🐍 reporter.py         # CSV report serialization
│   └── 🐍 visualizer.py       # Matplotlib dashboard generation
├── 📁 output/                 # Automatically generated artifacts
│   ├── 📊 audit_report.csv
│   └── 📈 dashboard.png
├── 📄 .gitignore
├── 🐍 main.py                 # Central orchestrator script
└── 📄 requirements.txt        # Project dependencies (PEP 508)
"""
=============================================================================
MODULE: visualizer.py
PURPOSE: Generates a high-res 3x3 All-in-One Dashboard (PNG) from compliance records.
=============================================================================
"""

import matplotlib.pyplot as plt
import numpy as np
from collections import Counter

def generate_dashboard(records: list, output_path: str, profile_name: str, timeframe: str):
    """Aggregiert die Daten und zeichnet das 3x3 Dashboard mit dynamischem Titel."""
    
    # 1. DATEN AGGREGIEREN
    statuses = Counter(r.get("status") for r in records)
    
    # Missing Fields (Flatten & filter)
    missing = Counter(f for r in records for f in r.get("missing_fields", []) if f != "None")
    
    # Languages
    langs = Counter(r.get("language") for r in records if r.get("language") != "Unknown")
    
    # Formats
    formats = Counter(f for r in records for f in r.get("file_formats", []) if f != "Unknown")
    
    # Disciplines (OEFOS + BK merged)
    disciplines = Counter(l for r in records for l in r.get("oefos_labels", []) + r.get("bk_labels", []) if l != "None")
    
    # GND Labels
    gnd = Counter(l for r in records for l in r.get("gnd_labels", []) if l != "None")
    
    # Trends (Yearly)
    years = sorted(list(set(r.get("year_published") for r in records if r.get("year_published") not in ["Unknown", None])))
    
    trend_status = {y: {"RED": 0, "GREEN": 0, "GOLD": 0} for y in years}
    trend_doi = {y: {"Internal": 0, "External": 0} for y in years}
    
    for r in records:
        y = r.get("year_published")
        if y in years:
            # Status Trend
            stat = r.get("status")
            if stat in trend_status[y]:
                trend_status[y][stat] += 1
                
            # DOI Trend
            if r.get("doi_internal") != "None":
                trend_doi[y]["Internal"] += 1
            ext_dois = [d for d in r.get("doi_external", []) if d != "None"]
            trend_doi[y]["External"] += len(ext_dois)

# 2. PLOTTING SETUP
    plt.style.use('bmh')
    fig, axes = plt.subplots(3, 3, figsize=(22, 16))
    
    # Dynamischen Titel generieren (Englisch & inkl. Grundgesamtheit)
    display_time = "All Time" if str(timeframe).lower() in ["all", "alle"] else str(timeframe)
    short_profile = "OER" if "OER" in profile_name else profile_name
    total_objects = len(records)
    
    dynamic_title = f"PMA - Summary - {short_profile} - {display_time}\nTotal Objects Audited: {total_objects}"
    
    # y-Wert und top-Margin anpassen, damit der 2-Zeiler nicht die Plots überlagert
    fig.suptitle(dynamic_title, fontsize=24, fontweight='bold', y=0.98)
    fig.subplots_adjust(top=0.92) 
    
    color_map = {"RED": "#e74c3c", "GREEN": "#2ecc71", "GOLD": "#f1c40f"}

    # --- ROW 1: STATUS, MISSING FIELDS, LANGUAGES ---
    
    # 1,1: Health Check (Donut)
    ax = axes[0, 0]
    labels = [s for s in ["RED", "GREEN", "GOLD"] if statuses[s] > 0]
    sizes = [statuses[s] for s in labels]
    colors = [color_map[s] for s in labels]
    if sizes:
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90, pctdistance=0.75)
        for text in texts + autotexts: text.set_fontsize(12)
        centre_circle = plt.Circle((0,0),0.50,fc='white')
        ax.add_artist(centre_circle)
    ax.set_title("Health Check (Status)", fontsize=16, fontweight='bold')

    # 1,2: Missing Fields (Bar Horizontal)
    ax = axes[0, 1]
    if missing:
        top_missing = missing.most_common(8)
        m_labels = [x[0] for x in top_missing][::-1]
        m_vals = [x[1] for x in top_missing][::-1]
        ax.barh(m_labels, m_vals, color="#34495e")
        ax.set_title("Top Error Sources (Missing/Invalid)", fontsize=16, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "No errors found", ha='center', va='center')
        ax.axis('off')

    # 1,3: Languages (Donut)
    ax = axes[0, 2]
    if langs:
        top_langs = langs.most_common(5)
        l_labels = [x[0] for x in top_langs]
        l_sizes = [x[1] for x in top_langs]
        wedges, texts, autotexts = ax.pie(l_sizes, labels=l_labels, autopct='%1.1f%%', startangle=90)
        centre_circle = plt.Circle((0,0),0.50,fc='white')
        ax.add_artist(centre_circle)
        ax.set_title("Languages (Top 5)", fontsize=16, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "No language data", ha='center', va='center')
        ax.axis('off')

    # --- ROW 2: TRENDS (COUPLED X-AXIS) ---
    
    # 2,1: Status over Time (Stacked Bar)
    ax = axes[1, 0]
    if years:
        reds = [trend_status[y]["RED"] for y in years]
        greens = [trend_status[y]["GREEN"] for y in years]
        golds = [trend_status[y]["GOLD"] for y in years]
        
        ax.bar(years, reds, color=color_map["RED"], label="RED")
        ax.bar(years, greens, bottom=reds, color=color_map["GREEN"], label="GREEN")
        ax.bar(years, golds, bottom=np.add(reds, greens), color=color_map["GOLD"], label="GOLD")
        
        ax.set_title("Quality Trend over Time", fontsize=16, fontweight='bold')
        ax.set_xticks(years)
        ax.tick_params(axis='x', rotation=45)
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No temporal data", ha='center', va='center')
        ax.axis('off')

    # 2,2: DOIs over Time (Stacked Bar)
    ax = axes[1, 1]
    if years:
        internals = [trend_doi[y]["Internal"] for y in years]
        externals = [trend_doi[y]["External"] for y in years]
        
        ax.bar(years, internals, color="#3498db", label="Internal DOIs")
        ax.bar(years, externals, bottom=internals, color="#9b59b6", label="External DOIs")
        
        ax.set_title("DOI Coverage over Time", fontsize=16, fontweight='bold')
        ax.set_xticks(years)
        ax.tick_params(axis='x', rotation=45)
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No DOI temporal data", ha='center', va='center')
        ax.axis('off')
        
    # 2,3: File Formats (Bar Horizontal - Top 5)
    ax = axes[1, 2]
    if formats:
        top_fmts = formats.most_common(5)
        f_labels = [x[0] for x in top_fmts][::-1]
        f_vals = [x[1] for x in top_fmts][::-1]
        ax.barh(f_labels, f_vals, color="#1abc9c")
        ax.set_title("File Formats (Top 5)", fontsize=16, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "No format data", ha='center', va='center')
        ax.axis('off')

    # --- ROW 3: DISCIPLINE & CONTENT ---
    
    # 3,1: Disciplines (OEFOS + BK merged)
    ax = axes[2, 0]
    if disciplines:
        top_disc = disciplines.most_common(10)
        d_labels = [x[0][:40] + "..." if len(x[0])>40 else x[0] for x in top_disc][::-1]
        d_vals = [x[1] for x in top_disc][::-1]
        ax.barh(d_labels, d_vals, color="#e67e22")
        ax.set_title("Top 10 Disciplines (OEFOS & BK)", fontsize=16, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "No discipline data", ha='center', va='center')
        ax.axis('off')

    # 3,2: GND Labels
    ax = axes[2, 1]
    if gnd:
        top_gnd = gnd.most_common(10)
        g_labels = [x[0][:40] + "..." if len(x[0])>40 else x[0] for x in top_gnd][::-1]
        g_vals = [x[1] for x in top_gnd][::-1]
        ax.barh(g_labels, g_vals, color="#e74c3c")
        ax.set_title("Top 10 GND Keywords", fontsize=16, fontweight='bold')
    else:
        ax.text(0.5, 0.5, "No GND data", ha='center', va='center')
        ax.axis('off')

    # 3,3: Placeholder for symmetry / Empty space intentionally left clean
    axes[2, 2].axis('off')

    # 3. RENDER & SAVE
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
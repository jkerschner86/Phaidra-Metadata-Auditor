import plotly.graph_objects as go
import os

def generate_advanced_demo():
    # 1. Simulierte Daten für zwei verschiedene Auswertungen
    # In der Realität berechnest du das aus deiner CSV
    labels_status = ["GREEN", "RED", "GOLD"]
    values_status = [45, 12, 5]
    colors_status = ["#22c55e", "#ef4444", "#eab308"]

    labels_formats = ["PDF", "XML", "JPG", "MP4"]
    values_formats = [30, 20, 10, 2]
    colors_formats = ["#3b82f6", "#f97316", "#06b6d4", "#8b5cf6"]

    # 2. Basis-Figur erstellen (Wir starten mit der Status-Ansicht)
    fig = go.Figure()

    # Trace 0: Status-Daten hinzufügen
    fig.add_trace(go.Pie(
        labels=labels_status, 
        values=values_status,
        marker=dict(colors=colors_status),
        hole=0.4,
        name="Status",
        visible=True # Startet sichtbar
    ))

    # Trace 1: Format-Daten hinzufügen
    fig.add_trace(go.Pie(
        labels=labels_formats, 
        values=values_formats,
        marker=dict(colors=colors_formats),
        hole=0.4,
        name="Formate",
        visible=False # Startet unsichtbar
    ))

    # 3. Dropdown-Menü (Updatemenus) konfigurieren
    fig.update_layout(
        title="Metadaten-Audit Interaktiv",
        updatemenus=[
            dict(
                active=0,
                buttons=list([
                    dict(
                        label="Ampel-Status",
                        method="update",
                        # Schaltet Trace 0 auf True, Trace 1 auf False
                        args=[{"visible": [True, False]},
                              {"title": "Verteilung: Ampel-Status"}]
                    ),
                    dict(
                        label="Dateiformate",
                        method="update",
                        # Schaltet Trace 0 auf False, Trace 1 auf True
                        args=[{"visible": [False, True]},
                              {"title": "Verteilung: Eingereichte Dateiformate"}]
                    ),
                ]),
                # Positionierung des Dropdowns
                direction="down",
                x=0.1,
                xanchor="left",
                y=1.1,
                yanchor="top"
            )
        ]
    )

    # 4. Export-Konfiguration für hochauflösende PNGs
    export_config = {
        'displaylogo': False, # Entfernt das Plotly-Logo aus der Leiste
        'toImageButtonOptions': {
            'format': 'png', 
            'filename': 'audit_export',
            'height': 800,
            'width': 1000,
            'scale': 2 # Erhöht die DPI für gestochen scharfe Exporte
        }
    }

    output_path = "interaktiver_report.html"
    # Die config wird beim Schreiben der HTML übergeben
    fig.write_html(output_path, config=export_config)
    
    print(f"[Erfolg] Erweiterte HTML generiert. Öffne '{output_path}'.")

if __name__ == "__main__":
    generate_advanced_demo()
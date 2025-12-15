from flask import Blueprint, render_template, send_file, Response
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
import requests
import csv
from io import StringIO

dashboard_bp = Blueprint("dashboard", __name__)
SHOPIFY_API_URL = "http://127.0.0.1:5000"


@dashboard_bp.route("/dashboard")
def dashboard():
    """Affiche le tableau de bord principal (statique)"""
    report_data = requests.get(f"{SHOPIFY_API_URL}/report").json()
    return render_template("dashboard_static.html", data=report_data)


@dashboard_bp.route("/dashboard/export/pdf")
def export_pdf():
    """Génère et télécharge le rapport Inventra au format PDF"""
    report_data = requests.get(f"{SHOPIFY_API_URL}/report").json()

    # Création d'un flux mémoire temporaire
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    for marque in report_data:
        # Titre de la marque
        elements.append(Paragraph(marque["Marque"], styles["Heading2"]))

        # En-tête du tableau
        data = [["Produit", "SKU", "Stock", "V60", "V120", "V180", "V365", "Suggestion (3m)", "Alerte"]]

        # Contenu du tableau
        for p in marque["Produits"]:
            data.append([
                p["Produit"], p["SKU"], p["Stock"], p["V60"], p["V120"],
                p["V180"], p["V365"], p["Suggestion (3m)"], p["Alerte"]
            ])

        # Style du tableau
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ]))
        elements.append(table)
        elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    # Génération du PDF
    doc.build(elements)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="Inventra_Rapport.pdf",
        mimetype="application/pdf"
    )


@dashboard_bp.route("/dashboard/export/csv")
def export_csv():
    """Exporte les données de toutes les marques en CSV (sans Suggestion)"""
    report_data = requests.get(f"{SHOPIFY_API_URL}/report").json()
    
    output = StringIO()
    writer = csv.writer(output)
    
    # En-têtes
    writer.writerow([
        'Marque',
        'Produit',
        'Stock',
        'Coût ($)',
        'V60',
        'V120',
        'V180',
        'V365',
        'Alerte'
    ])
    
    # Données pour toutes les marques
    for marque in report_data:
        marque_nom = marque.get('Marque', '')
        totaux = marque.get('Totaux', {})
        
        # ✅ Ligne totaux - utiliser les VRAIES clés de votre structure
        writer.writerow([
            f"💰 TOTAUX - {marque_nom}",
            'Net Sales',
            round(totaux.get('Valeur Stock Total ($)', 0)),
            round(totaux.get('Coût Total ($)', 0)),
            round(totaux.get('Montant V60 Total ($)', 0)),
            round(totaux.get('Montant V120 Total ($)', 0)),
            round(totaux.get('Montant V180 Total ($)', 0)),
            round(totaux.get('Montant V365 Total ($)', 0)),
            ''
        ])
        
        # Produits de la marque
        for produit in marque.get('Produits', []):
            writer.writerow([
                marque_nom,
                produit.get('Produit', ''),
                produit.get('Stock', 0),
                f"{produit.get('Coût par article ($)', 0):.2f}",
                produit.get('V60', 0),
                produit.get('V120', 0),
                produit.get('V180', 0),
                produit.get('V365', 0),
                produit.get('Alerte', '')
            ])
        
        # Ligne vide entre marques
        writer.writerow([])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=inventra_toutes_marques.csv'}
    )




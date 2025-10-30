from flask import Blueprint, render_template, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
import requests

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

    # Création d’un flux mémoire temporaire
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


from flask import Blueprint, render_template, send_file, Response, request
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
import requests
import csv
from io import StringIO
import os
from dotenv import load_dotenv

# ✅ Charger les variables d'environnement
load_dotenv()

dashboard_bp = Blueprint("dashboard", __name__)

# ✅ Configuration identique à app.py
SHOP_NAME = os.getenv("SHOP_NAME")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
API_VER = "2024-10"
BASE_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{API_VER}"
HEADERS = {"X-Shopify-Access-Token": ACCESS_TOKEN, "Content-Type": "application/json"}

print(f"🏪 Shop: {SHOP_NAME}")


def get_api_url():
    """Retourne l'URL de base de l'API selon l'environnement"""
    try:
        # Utiliser l'URL de la requête actuelle
        return request.url_root.rstrip('/')
    except:
        # Fallback si pas de contexte de requête
        return os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:5000")


@dashboard_bp.route("/dashboard")
def dashboard():
    """Affiche le tableau de bord principal (statique)"""
    SHOPIFY_API_URL = get_api_url()
    report_data = requests.get(f"{SHOPIFY_API_URL}/report").json()
    return render_template("dashboard_static.html", data=report_data)


@dashboard_bp.route("/dashboard/export/pdf")
def export_pdf():
    """Génère et télécharge le rapport Inventra au format PDF"""
    SHOPIFY_API_URL = get_api_url()
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
                p["Produit"], p.get("SKU", ""), p["Stock"], p["V60"], p["V120"],
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
    try:
        print("🔄 Début export CSV...")
        
        # ✅ Utiliser l'URL de la requête actuelle
        SHOPIFY_API_URL = get_api_url()
        print(f"🌐 API URL: {SHOPIFY_API_URL}")
        
        # ✅ Requête HTTP vers /report
        report_data = requests.get(f"{SHOPIFY_API_URL}/report", timeout=30).json()
        
        print(f"✅ Données récupérées: {len(report_data)} marques")
        
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
            
            print(f"📊 Export marque: {marque_nom}")
            
            # Ligne totaux
            writer.writerow([
                f"TOTAUX - {marque_nom}",
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
        
        print("✅ CSV généré avec succès")
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=inventra_toutes_marques.csv'}
        )
        
    except Exception as e:
        print(f"❌ ERREUR EXPORT CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Erreur lors de la génération du CSV: {str(e)}", 500

from flask import Blueprint, jsonify
from services.shopify_api import shopify_get_all

products_bp = Blueprint("products", __name__)

# === 📊 Fonction de génération des données (sans HTTP) ===

def generate_products_data():
    """Génère les données des produits (logique métier pure)"""
    try:
        data = shopify_get_all("products.json")
        return data
    except Exception as e:
        raise Exception(f"Erreur de connexion à Shopify : {e}")

# === 🌐 Endpoint HTTP (mince wrapper) ===

@products_bp.route("/data/products")
def get_products():
    """Endpoint HTTP pour la liste des produits"""
    try:
        data = generate_products_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Erreur de génération des produits : {e}"}), 500
        # from flask import Blueprint, jsonify
# from services.shopify_api import shopify_get
# from services.shopify_api import shopify_get_all

# products_bp = Blueprint("products", __name__)

# @products_bp.route("/data/products")
# def get_products():
#     """Liste des produits"""
#     data = shopify_get_all("products.json")
#     return jsonify(data)

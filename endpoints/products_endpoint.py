from flask import Blueprint, jsonify
from services.shopify_api import shopify_get
from services.shopify_api import shopify_get_all

products_bp = Blueprint("products", __name__)

@products_bp.route("/data/products")
def get_products():
    """Liste des produits"""
    data = shopify_get_all("products.json")
    return jsonify(data)

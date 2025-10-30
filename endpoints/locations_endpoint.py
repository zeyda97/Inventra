from flask import Blueprint, jsonify
from services.shopify_api import shopify_get
import requests

locations_bp = Blueprint("locations", __name__)

@locations_bp.route("/data/locations")
def get_locations():
    """Liste des lieux / entrepôts"""
    try:
        data = shopify_get("locations.json")
        return jsonify(data)
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"Erreur Shopify : {str(e)}"})

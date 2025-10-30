from flask import Blueprint, jsonify
from services.shopify_api import shopify_get_all

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("/inventory/enriched")
def inventory_enriched_for_report():
    """
    ✅ Version simplifiée et fiable de l’inventaire pour Shopify Prestige.
    Récupère toutes les variantes de produits avec :
    - Marque
    - Produit (titre + variante)
    - SKU
    - Variant ID (identifiant unique)
    - Stock actuel
    - Prix unitaire
    """
    try:
        products = shopify_get_all("products.json", {"limit": 250}, root_key="products")
    except Exception as e:
        return jsonify({"error": f"Erreur de connexion à Shopify : {e}"}), 500

    rows = []
    for p in products:
        brand = p.get("vendor", "Inconnue")
        title = p.get("title", "").strip()

        for v in p.get("variants", []):
            rows.append({
                "Marque": brand,
                "Produit": f"{title} {v.get('title') or ''}".strip(),
                "SKU": v.get("sku"),
                "Variant ID": str(v.get("id")),  # ✅ identifiant unique de la variante
                "Stock actuel": v.get("inventory_quantity", 0),
                "Prix unitaire ($)": float(v.get("price") or 0)
            })

    return jsonify(rows)


@inventory_bp.route("/data/inventory")
def get_inventory_grouped():
    """
    ✅ Version groupée de l’inventaire par SKU.
    Fournit un résumé : stock total, prix, marque et produit.
    """
    try:
        products = shopify_get_all("products.json", {"limit": 250}, root_key="products")
    except Exception as e:
        return jsonify({"error": f"Erreur de connexion à Shopify : {e}"}), 500

    grouped = {}

    for p in products:
        brand = p.get("vendor", "Inconnue")
        title = p.get("title", "").strip()

        for v in p.get("variants", []):
            sku = v.get("sku")
            if not sku:
                continue

            stock = v.get("inventory_quantity", 0) or 0
            price = float(v.get("price") or 0)

            if sku not in grouped:
                grouped[sku] = {
                    "Marque": brand,
                    "Produit": f"{title} {v.get('title') or ''}".strip(),
                    "Prix unitaire ($)": price,
                    "Stock total": stock
                }
            else:
                grouped[sku]["Stock total"] += stock  # cas rare : SKU répété

    grouped_list = [{"SKU": sku, **vals} for sku, vals in grouped.items()]
    return jsonify(grouped_list)


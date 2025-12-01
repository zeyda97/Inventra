from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from services.shopify_api import shopify_get_all

orders_bp = Blueprint("orders", __name__)

def generate_orders_data():
    """
    Récupère TOUTES les commandes des 365 derniers jours
    Compatible avec Shopify Analytics (pas de filtres restrictifs)
    """
    since = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")
    
    params = {
        "status": "any",  # ✅ Toutes les commandes (ouvertes, fermées, annulées)
        "created_at_min": since,
        "limit": 250,
        "order": "created_at asc",
        # ✅ PAS de financial_status ni fulfillment_status
        # Shopify Analytics compte TOUTES les commandes
    }

    try:
        orders = shopify_get_all("orders.json", params, root_key="orders")
        print(f"📦 Total commandes récupérées : {len(orders)}")
    except Exception as e:
        raise Exception(f"Erreur de connexion à Shopify : {e}")

    result = []

    for o in orders:
        line_items = []
        
        for li in o.get("line_items", []):
            sku = li.get("sku")
            variant_id = li.get("variant_id")
            quantity = li.get("quantity", 0) or 0
            price = float(li.get("price") or 0)
            gross_sales = quantity * price
            discount = float(li.get("total_discount") or 0)

            # ✅ Calcul des remboursements (refunds)
            refunded_qty = 0
            refunded_amount = 0
            
            for refund in o.get("refunds", []):
                for r_li in refund.get("refund_line_items", []):
                    if r_li.get("line_item_id") == li.get("id"):
                        refunded_qty += r_li.get("quantity", 0) or 0
                        refunded_amount += float(r_li.get("subtotal") or 0)

            # ✅ Net sales = gross - discounts - refunds
            net_sales = gross_sales - discount - refunded_amount
            
            # ✅ Quantité nette = quantité commandée - quantité remboursée
            net_quantity = quantity - refunded_qty

            line_items.append({
                "sku": sku,
                "product_id": li.get("product_id"),
                "variant_id": variant_id,
                "quantity": net_quantity,  # ✅ IMPORTANT : quantité NETTE (après remboursements)
                "gross_sales": gross_sales,
                "discounts": discount,
                "refunds": refunded_amount,
                "returned_quantity": refunded_qty,
                "net_sales": net_sales,
                "taxes": float(li.get("total_tax") or 0),
                "shipping_allocation": float(li.get("total_shipping") or 0),
            })

        result.append({
            "id": o.get("id"),
            "name": o.get("name"),
            "created_at": o.get("created_at"),
            "currency": o.get("currency"),
            "total_price": float(o.get("current_total_price") or 0),
            "financial_status": o.get("financial_status"),
            "fulfillment_status": o.get("fulfillment_status"),
            "line_items": line_items,
        })

    print(f"📊 Total line_items traités : {sum(len(o['line_items']) for o in result)}")
    return {"orders": result}

@orders_bp.route("/data/orders")
def get_orders():
    """Endpoint HTTP pour les commandes"""
    try:
        data = generate_orders_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Erreur : {e}"}), 500


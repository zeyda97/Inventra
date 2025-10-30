from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from services.shopify_api import shopify_get_all

orders_bp = Blueprint("orders", __name__)

@orders_bp.route("/data/orders")
def get_orders():
    since = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "status": "any",
        "financial_status": "paid",
        "fulfillment_status": "shipped",
        "created_at_min": since,
        "limit": 250,
        "order": "created_at asc",
    }
    orders = shopify_get_all("orders.json", params, root_key="orders")

    result = []
    for o in orders:
        items = [{
            "name": li.get("name"),
            "sku": li.get("sku"),
            "quantity": li.get("quantity", 0),
            "price": float(li.get("price") or 0),
            "product_id": li.get("product_id"),
            "variant_id": li.get("variant_id"),
        } for li in o.get("line_items", [])]
        result.append({
            "id": o.get("id"),
            "name": o.get("name"),
            "created_at": o.get("created_at"),
            "currency": o.get("currency"),
            "total_price": float(o.get("current_total_price") or 0),
            "financial_status": o.get("financial_status"),
            "line_items": items,
        })
    return jsonify({"orders": result})


from flask import Blueprint, jsonify
import requests
import unicodedata
from datetime import datetime, timedelta
from collections import defaultdict

report_bp = Blueprint("report", __name__)
BASE = "http://127.0.0.1:5000"


# === 🔧 Fonctions utilitaires ===
def normalize_text(text):
    """Nettoie et uniformise les textes pour faciliter les correspondances"""
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.replace("-", " ").replace("_", " ")
    text = " ".join(text.split())
    return text


# === 📊 Route principale du reporting ===
@report_bp.route("/report")
def report():
    """Combine inventaire, commandes et produits en un rapport consolidé"""
    try:
        inventory = requests.get(f"{BASE}/inventory/enriched").json()
        orders = requests.get(f"{BASE}/data/orders").json().get("orders", [])
    except Exception as e:
        return jsonify({"error": f"Erreur de connexion à une source : {e}"}), 500

    # --- Index inventaire ---
    inventory_by_variant = {str(p.get("Variant ID")): p for p in inventory if p.get("Variant ID")}
    inventory_by_sku = {normalize_text(p.get("SKU")): p for p in inventory if p.get("SKU")}
    inventory_by_name = {normalize_text(p.get("Produit")): p for p in inventory}

    # --- Fenêtres temporelles pour les ventes ---
    now = datetime.utcnow()
    periods = {
        "V60": now - timedelta(days=60),
        "V120": now - timedelta(days=120),
        "V180": now - timedelta(days=180),
        "V365": now - timedelta(days=365),
    }

    # --- Dictionnaire des ventes cumulées ---
    sales_data = {}

    for order in orders:
        created_at = order.get("created_at")
        if not created_at:
            continue
        try:
            order_date = datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            continue

        for item in order.get("line_items", []):
            variant_id = str(item.get("variant_id"))
            sku = normalize_text(item.get("sku"))
            name = normalize_text(item.get("name"))
            qty = item.get("quantity", 0) or 0

            # 🧩 Trouver la correspondance la plus fiable
            key = None
            if variant_id in inventory_by_variant:
                key = variant_id
            elif sku in inventory_by_sku:
                key = sku
            else:
                for inv_name in inventory_by_name.keys():
                    if inv_name in name or name in inv_name:
                        key = inv_name
                        break
            if not key:
                continue

            # Initialiser la structure
            if key not in sales_data:
                sales_data[key] = {"V60": 0, "V120": 0, "V180": 0, "V365": 0}

            # Incrémenter selon la période
            if order_date >= periods["V60"]:
                sales_data[key]["V60"] += qty
            if order_date >= periods["V120"]:
                sales_data[key]["V120"] += qty
            if order_date >= periods["V180"]:
                sales_data[key]["V180"] += qty
            if order_date >= periods["V365"]:
                sales_data[key]["V365"] += qty

    # === Construction du rapport final ===
    report_data = []
    for product in inventory:
        variant_id = str(product.get("Variant ID"))
        sku = normalize_text(product.get("SKU"))
        name = normalize_text(product.get("Produit"))

        # Trouver les ventes liées à ce produit
        key = (
            variant_id
            if variant_id in sales_data
            else sku
            if sku in sales_data
            else name
        )
        ventes = sales_data.get(key, {"V60": 0, "V120": 0, "V180": 0, "V365": 0})

        # ✅ Correction des stocks négatifs ou None
        raw_stock = product.get("Stock actuel", 0)
        stock = 0 if raw_stock is None or raw_stock < 0 else raw_stock

        produit_report = {
            "Marque": product.get("Marque"),
            "Produit": product.get("Produit"),
            "SKU": product.get("SKU"),
            "Variant ID": variant_id,
            "Stock": stock,
            "Prix unitaire ($)": product.get("Prix unitaire ($)", 0),
            "V60": ventes["V60"],
            "V120": ventes["V120"],
            "V180": ventes["V180"],
            "V365": ventes["V365"],
            "Suggestion (3m)": max(0, round(ventes["V180"] / 3 - stock, 2)),
            "Alerte": "✅ OK" if stock > 0 else "🚨 Rupture",
        }
        report_data.append(produit_report)

    # === Regroupement par marque ===
    marques = defaultdict(lambda: {"Marque": "", "Produits": []})
    for r in report_data:
        marque = (r.get("Marque") or "Inconnue").strip()
        marques[marque]["Marque"] = marque
        marques[marque]["Produits"].append({
            "Produit": r.get("Produit"),
            "SKU": r.get("SKU"),
            "Variant ID": r.get("Variant ID"),
            "Stock": r.get("Stock"),
            "Prix unitaire ($)": r.get("Prix unitaire ($)"),
            "V60": r.get("V60"),
            "V120": r.get("V120"),
            "V180": r.get("V180"),
            "V365": r.get("V365"),
            "Suggestion (3m)": r.get("Suggestion (3m)"),
            "Alerte": r.get("Alerte")
        })

    grouped_report = list(marques.values())
    return jsonify(grouped_report)


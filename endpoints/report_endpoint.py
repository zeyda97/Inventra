from flask import Blueprint, jsonify
from endpoints.inventory_endpoint import generate_inventory_data
from endpoints.orders_endpoint import generate_orders_data
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import time

report_bp = Blueprint("report", __name__)

# Cache pour éviter les appels API répétés
product_cache = {}

def get_product_info_from_api(product_id):
    """
    Récupère les infos d'un produit (même supprimé) via l'API Shopify
    """
    if not product_id:
        return {"title": "Produit inconnu", "vendor": "Marque inconnue"}
    
    try:
        from services.shopify_api import shopify_get
        response = shopify_get(f"products/{product_id}.json")
        
        if response and "product" in response:
            p = response["product"]
            return {
                "title": p.get("title", "Produit inconnu"),
                "vendor": p.get("vendor", "Marque inconnue")
            }
    except Exception as e:
        print(f"   ⚠️ Impossible de récupérer product_id {product_id}: {e}")
    
    return {"title": f"Produit {product_id}", "vendor": "Marque inconnue"}


def generate_report_data():
    """
    Génère le rapport complet avec inventaire et ventes
    Aligné avec Shopify Analytics via GraphQL
    """
    start = time.time()
    
    print(f"\n{'='*80}")
    print(f"🚀 GÉNÉRATION DU RAPPORT")
    print(f"{'='*80}\n")
    
    # ✅ ÉTAPE 1 : Récupérer l'inventaire (avec coûts via GraphQL)
    print("📦 Chargement de l'inventaire...")
    inventory = generate_inventory_data()
    print(f"✅ {len(inventory)} variantes chargées\n")
    
    # ✅ ÉTAPE 2 : Récupérer les commandes (via GraphQL)
    print("📦 Chargement des commandes...")
    orders_data = generate_orders_data()
    orders = orders_data.get("orders", [])
    print(f"✅ {len(orders)} commandes chargées\n")
    
    # ✅ ÉTAPE 3 : Calculer les dates des périodes (avec timezone UTC)
    now = datetime.now(timezone.utc)
    cutoff_60 = now - timedelta(days=60)
    cutoff_120 = now - timedelta(days=120)
    cutoff_180 = now - timedelta(days=180)
    cutoff_365 = now - timedelta(days=365)
    
    print(f"📅 Périodes de ventes:")
    print(f"   V60  : depuis {cutoff_60.strftime('%Y-%m-%d')}")
    print(f"   V120 : depuis {cutoff_120.strftime('%Y-%m-%d')}")
    print(f"   V180 : depuis {cutoff_180.strftime('%Y-%m-%d')}")
    print(f"   V365 : depuis {cutoff_365.strftime('%Y-%m-%d')}\n")
    
    # ✅ ÉTAPE 4 : Créer un mapping de l'inventaire par variant_id
    inventory_by_variant_id = {}
    for p in inventory:
        vid = p.get("Variant ID")
        if vid is not None:
            inventory_by_variant_id[str(vid)] = p
    
    print(f"🔑 Mapping inventaire : {len(inventory_by_variant_id)} variants\n")
    
    # ✅ ÉTAPE 5 : Agréger les ventes par variant_id
    sales_by_variant = defaultdict(lambda: {
        "V60": 0,
        "V120": 0,
        "V180": 0,
        "V365": 0,
        "montant_v60": 0.0,
        "montant_v120": 0.0,
        "montant_v180": 0.0,
        "montant_v365": 0.0,
        "gross_sales": 0.0,
        "discounts": 0.0,
        "net_sales": 0.0
    })
    
    # ✅ NOUVEAU : Stockage des variants supprimés avec regroupement par nom complet
    deleted_variants_by_name = defaultdict(lambda: {
        "Marque": "",
        "Produit": "",
        "SKU": "",
        "variant_ids": [],  # Liste des variant_ids regroupés
        "Prix unitaire ($)": 0.0,
        "Coût par article ($)": 0.0
    })
    
    print("📊 Agrégation des ventes par variant...\n")
    
    for order in orders:
        # ✅ Parser la date avec timezone
        order_date_str = order["created_at"]
        if order_date_str.endswith('Z'):
            order_date_str = order_date_str.replace('Z', '+00:00')
        order_date = datetime.fromisoformat(order_date_str)
        
        # S'assurer que order_date a une timezone
        if order_date.tzinfo is None:
            order_date = order_date.replace(tzinfo=timezone.utc)
        
        for item in order["line_items"]:
            variant_id = item.get("variant_id")
            product_id = item.get("product_id")
            sku_from_order = item.get("sku")
            
            if not variant_id:
                continue
            
            variant_id_str = str(variant_id)
            
            # ✅ DÉTECTER LES VARIANTS SUPPRIMÉS
            if variant_id_str not in inventory_by_variant_id:
                # C'est un variant supprimé !
                
                # Utiliser le cache pour éviter les appels API répétés
                if product_id and product_id not in product_cache:
                    product_cache[product_id] = get_product_info_from_api(product_id)
                
                product_info = product_cache.get(product_id, {"title": "Produit inconnu", "vendor": "Marque inconnue"})
                product_title = product_info["title"]
                vendor = product_info["vendor"]
                
                # ✅ RÉCUPÉRER LE VARIANT TITLE depuis les line_items
                variant_title = item.get("variant_title") or item.get("name") or ""
                
                # ✅ CONSTRUIRE LE NOM COMPLET : "The Orchid Man 100ml"
                if variant_title and variant_title != "Default Title":
                    # Si le variant_title contient déjà le product_title, ne pas dupliquer
                    if product_title.lower() in variant_title.lower():
                        full_product_name = variant_title
                    else:
                        full_product_name = f"{product_title} {variant_title}".strip()
                else:
                    full_product_name = product_title
                
                # ✅ REGROUPER par nom complet
                if full_product_name not in deleted_variants_by_name:
                    deleted_variants_by_name[full_product_name] = {
                        "Marque": vendor,
                        "Produit": full_product_name,
                        "SKU": sku_from_order or "N/A",
                        "variant_ids": [variant_id_str],
                        "Prix unitaire ($)": float(item.get("price", 0) or 0),
                        "Coût par article ($)": 0
                    }
                    print(f"🗑️ Variant supprimé : {vendor} - {full_product_name} (SKU: {sku_from_order or 'N/A'})")
                else:
                    # Ajouter ce variant_id au groupe existant
                    if variant_id_str not in deleted_variants_by_name[full_product_name]["variant_ids"]:
                        deleted_variants_by_name[full_product_name]["variant_ids"].append(variant_id_str)
            
            # ✅ AGRÉGER LES VENTES
            quantity = item.get("quantity", 0)
            net_sales = item.get("net_sales", 0.0)
            gross_sales = item.get("gross_sales", 0.0)
            discounts = item.get("discounts", 0.0)
            
            # Agréger par période
            if order_date >= cutoff_60:
                sales_by_variant[variant_id_str]["V60"] += quantity
                sales_by_variant[variant_id_str]["montant_v60"] += net_sales
            
            if order_date >= cutoff_120:
                sales_by_variant[variant_id_str]["V120"] += quantity
                sales_by_variant[variant_id_str]["montant_v120"] += net_sales
            
            if order_date >= cutoff_180:
                sales_by_variant[variant_id_str]["V180"] += quantity
                sales_by_variant[variant_id_str]["montant_v180"] += net_sales
            
            if order_date >= cutoff_365:
                sales_by_variant[variant_id_str]["V365"] += quantity
                sales_by_variant[variant_id_str]["montant_v365"] += net_sales
                sales_by_variant[variant_id_str]["gross_sales"] += gross_sales
                sales_by_variant[variant_id_str]["discounts"] += discounts
                sales_by_variant[variant_id_str]["net_sales"] += net_sales
    
    print(f"✅ {len(sales_by_variant)} variants avec ventes")
    print(f"🗑️ {len(deleted_variants_by_name)} produits supprimés uniques détectés\n")
    
    # ✅ ÉTAPE 6 : Construire le rapport
    report = []
    total_net_items_sold = 0
    total_net_sales = 0.0
    total_net_items_sold_deleted = 0
    total_net_sales_deleted = 0.0
    
    print("📊 Construction du rapport...\n")
    
    # Produits actuels
    for p in inventory:
        variant_id = str(p.get("Variant ID"))
        ventes = sales_by_variant.get(variant_id, {
            "V60": 0, "V120": 0, "V180": 0, "V365": 0,
            "montant_v60": 0.0, "montant_v120": 0.0,
            "montant_v180": 0.0, "montant_v365": 0.0,
            "gross_sales": 0.0, "discounts": 0.0, "net_sales": 0.0
        })
        
        stock = p.get("Stock actuel") or 0
        stock = stock if stock > 0 else 0
        
        prix_vente = p.get("Prix unitaire ($)", 0)
        cout_unitaire = p.get("Coût par article ($)", 0)
        
        valeur_stock = stock * cout_unitaire
        
        total_net_items_sold += ventes["V365"]
        total_net_sales += ventes["net_sales"]
        
        report.append({
            "Marque": p.get("Marque"),
            "Produit": p.get("Produit"),
            "SKU": p.get("SKU"),
            "Variant ID": p.get("Variant ID"),
            "Stock": stock,
            "Prix unitaire ($)": prix_vente,
            "Coût par article ($)": cout_unitaire,
            "Coût estimé": False,
            "Valeur Stock ($)": round(valeur_stock, 2),
            "V60": ventes["V60"],
            "V120": ventes["V120"],
            "V180": ventes["V180"],
            "V365": ventes["V365"],
            "Montant V60 ($)": round(ventes["montant_v60"], 2),
            "Montant V120 ($)": round(ventes["montant_v120"], 2),
            "Montant V180 ($)": round(ventes["montant_v180"], 2),
            "Montant V365 ($)": round(ventes["montant_v365"], 2),
            "Gross Sales": round(ventes["gross_sales"], 2),
            "Discounts": round(ventes["discounts"], 2),
            "Net Sales": round(ventes["net_sales"], 2),
            "Suggestion (3m)": max(0, round(ventes["V180"] / 3 - stock, 2)),
            "Alerte": "✅ OK" if stock > 0 else "🚨 Rupture",
            "is_deleted": False
        })
    
    # ✅ Produits supprimés (regroupés par nom)
    print(f"📊 Ajout des {len(deleted_variants_by_name)} produits supprimés regroupés...\n")
    
    for product_name, deleted_info in deleted_variants_by_name.items():
        # ✅ AGRÉGER les ventes de tous les variant_ids de ce groupe
        ventes_aggregated = {
            "V60": 0, "V120": 0, "V180": 0, "V365": 0,
            "montant_v60": 0.0, "montant_v120": 0.0,
            "montant_v180": 0.0, "montant_v365": 0.0,
            "gross_sales": 0.0, "discounts": 0.0, "net_sales": 0.0
        }
        
        for vid in deleted_info["variant_ids"]:
            ventes = sales_by_variant.get(vid, {})
            for key in ventes_aggregated.keys():
                ventes_aggregated[key] += ventes.get(key, 0)
        
        total_net_items_sold += ventes_aggregated["V365"]
        total_net_sales += ventes_aggregated["net_sales"]
        total_net_items_sold_deleted += ventes_aggregated["V365"]
        total_net_sales_deleted += ventes_aggregated["net_sales"]
        
        # ✅ Utiliser le premier variant_id comme représentant
        representative_variant_id = deleted_info["variant_ids"][0] if deleted_info["variant_ids"] else "N/A"
        
        report.append({
            "Marque": deleted_info["Marque"],
            "Produit": f"🗑️ {deleted_info['Produit']}",  # ✅ Nom complet avec variante
            "SKU": deleted_info["SKU"],
            "Variant ID": representative_variant_id,
            "Stock": 0,
            "Prix unitaire ($)": deleted_info["Prix unitaire ($)"],
            "Coût par article ($)": deleted_info["Coût par article ($)"],
            "Coût estimé": False,
            "Valeur Stock ($)": 0,
            "V60": ventes_aggregated["V60"],
            "V120": ventes_aggregated["V120"],
            "V180": ventes_aggregated["V180"],
            "V365": ventes_aggregated["V365"],
            "Montant V60 ($)": round(ventes_aggregated["montant_v60"], 2),
            "Montant V120 ($)": round(ventes_aggregated["montant_v120"], 2),
            "Montant V180 ($)": round(ventes_aggregated["montant_v180"], 2),
            "Montant V365 ($)": round(ventes_aggregated["montant_v365"], 2),
            "Gross Sales": round(ventes_aggregated["gross_sales"], 2),
            "Discounts": round(ventes_aggregated["discounts"], 2),
            "Net Sales": round(ventes_aggregated["net_sales"], 2),
            "Suggestion (3m)": 0,
            "Alerte": "🗑️ SUPPRIMÉ",
            "is_deleted": True
        })
    
    print(f"✅ {len([r for r in report if r.get('is_deleted')])} produits supprimés ajoutés au rapport\n")
    
    # ✅ ÉTAPE 7 : Grouper par marque
    grouped = defaultdict(lambda: {
        "Marque": "",
        "Produits": [],
        "Totaux": {
            "Valeur Stock Total ($)": 0,
            "Coût Total ($)": 0,
            "Montant V60 Total ($)": 0,
            "Montant V120 Total ($)": 0,
            "Montant V180 Total ($)": 0,
            "Montant V365 Total ($)": 0
        }
    })
    
    for row in report:
        brand = row.get("Marque") or "Inconnue"
        grouped[brand]["Marque"] = brand
        grouped[brand]["Produits"].append(row)
        
        grouped[brand]["Totaux"]["Valeur Stock Total ($)"] += row["Valeur Stock ($)"]
        grouped[brand]["Totaux"]["Coût Total ($)"] += row["Stock"] * row["Coût par article ($)"]
        grouped[brand]["Totaux"]["Montant V60 Total ($)"] += row["Montant V60 ($)"]
        grouped[brand]["Totaux"]["Montant V120 Total ($)"] += row["Montant V120 ($)"]
        grouped[brand]["Totaux"]["Montant V180 Total ($)"] += row["Montant V180 ($)"]
        grouped[brand]["Totaux"]["Montant V365 Total ($)"] += row["Montant V365 ($)"]
    
    for brand_data in grouped.values():
        for key in brand_data["Totaux"]:
            brand_data["Totaux"][key] = round(brand_data["Totaux"][key], 2)
    
    # ✅ ÉTAPE 8 : Afficher la comparaison avec Shopify
    print(f"{'='*80}")
    print(f"📊 COMPARAISON AVEC SHOPIFY (365 jours)")
    print(f"{'='*80}")
    print(f"Net Items Sold:")
    print(f"   Shopify  : 8,250 unités")
    print(f"   Inventra : {total_net_items_sold:,} unités")
    print(f"   - Actuels: {total_net_items_sold - total_net_items_sold_deleted:,} unités")
    print(f"   - Supprimés: {total_net_items_sold_deleted:,} unités")
    print(f"   Différence : {8250 - total_net_items_sold:,} unités")
    if total_net_items_sold > 0:
        print(f"   Précision: {(total_net_items_sold / 8250 * 100):.1f}%")
    print(f"\nNet Sales:")
    print(f"   Shopify  : 451,658.59 $")
    print(f"   Inventra : {total_net_sales:,.2f} $")
    print(f"   - Actuels: {total_net_sales - total_net_sales_deleted:,.2f} $")
    print(f"   - Supprimés: {total_net_sales_deleted:,.2f} $")
    print(f"   Différence : {451658.59 - total_net_sales:,.2f} $")
    if total_net_sales > 0:
        print(f"   Précision: {(total_net_sales / 451658.59 * 100):.1f}%")
    print(f"{'='*80}\n")
    
    print(f"⏱ Rapport généré en {time.time() - start:.2f}s\n")
    
    return list(grouped.values())


@report_bp.route("/report")
def get_report():
    """Endpoint HTTP pour le rapport complet"""
    try:
        data = generate_report_data()
        return jsonify(data)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Erreur complète:\n{error_detail}")
        return jsonify({"error": f"Erreur : {e}"}), 500
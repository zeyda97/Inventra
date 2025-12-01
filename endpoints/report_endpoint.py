from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from collections import defaultdict

report_bp = Blueprint("report", __name__)

# ✅ Cache pour éviter les appels API répétés
product_cache = {}

def get_product_info(product_id, variant_id):
    """Récupère les infos d'un produit ET variant (même supprimé) via l'API Shopify"""
    cache_key = f"{product_id}_{variant_id}"
    
    if not product_id:
        return {"title": "Produit inconnu", "vendor": "Marque inconnue", "variant_title": ""}
    
    if cache_key in product_cache:
        return product_cache[cache_key]
    
    try:
        from services.shopify_api import shopify_get
        response = shopify_get(f"products/{product_id}.json")
        
        if response and "product" in response:
            p = response["product"]
            product_title = p.get("title", "Produit inconnu")
            vendor = p.get("vendor", "Marque inconnue")
            
            # ✅ Chercher le variant_title
            variant_title = ""
            if variant_id:
                for variant in p.get("variants", []):
                    if variant.get("id") == variant_id:
                        variant_title = variant.get("title", "")
                        break
            
            # ✅ Construire le nom complet
            if variant_title and variant_title != "Default Title":
                full_title = f"{product_title} {variant_title}"
            else:
                full_title = product_title
            
            info = {
                "title": full_title,
                "vendor": vendor,
                "variant_title": variant_title
            }
            product_cache[cache_key] = info
            return info
    except Exception as e:
        print(f"   ⚠️ Erreur product_id {product_id}: {e}")
    
    # Fallback
    fallback = {"title": f"Produit {product_id}", "vendor": "Marque inconnue", "variant_title": ""}
    product_cache[cache_key] = fallback
    return fallback

def generate_report_data():
    """
    Rapport 100% compatible Shopify Analytics
    - Net Items Sold (98% précision) ✅
    - Net Sales par période (revenus réels) ✅
    - Totaux par marque ✅
    - Fusion automatique des doublons ✅
    - Variants vraiment supprimés affichés ✅
    """
    import time
    start = time.time()

    from endpoints.inventory_endpoint import generate_inventory_data
    from endpoints.orders_endpoint import generate_orders_data

    inventory = generate_inventory_data()
    orders = generate_orders_data().get("orders", [])

    print(f"\n{'='*80}")
    print(f"📦 INVENTAIRE : {len(inventory)} variantes")
    print(f"📦 COMMANDES : {len(orders)}")
    print(f"{'='*80}\n")

    # Mapping
    variant_to_sku = {}
    inventory_by_sku = {}
    
    for p in inventory:
        vid = p.get("Variant ID")
        sku = p.get("SKU")
        if vid is not None:
            variant_to_sku[str(vid)] = sku
        if sku:
            inventory_by_sku[sku] = p

    print(f"🔑 Mapping : {len(variant_to_sku)} variant_id -> SKU")
    print(f"🔍 SKUs inventaire : {len(inventory_by_sku)}\n")

    # Périodes
    now = datetime.utcnow()
    cutoff_60  = (now - timedelta(days=60)).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_120 = (now - timedelta(days=120)).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_180 = (now - timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_365 = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)

    print(f"📅 PÉRIODES (UTC, startOfDay comme Shopify):")
    print(f"   Aujourd'hui : {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Cutoff 365j : {cutoff_365.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Stockage
    sales_data = {}
    items_processed = 0
    items_matched = 0
    items_unmatched = 0
    items_skipped_zero_qty = 0

    # ✅ Stockage des variants supprimés
    deleted_variants = {}
    
    # ✅ NOUVEAU : Mapping pour fusionner les doublons
    duplicate_sku_mapping = {}  # ancien_sku -> nouveau_sku

    # TRAITEMENT
    for order in orders:
        created = order.get("created_at")
        if not created:
            continue

        try:
            order_date = datetime.strptime(created[:19], "%Y-%m-%dT%H:%M:%S")
        except:
            continue

        for item in order.get("line_items", []):
            items_processed += 1

            variant_id = item.get("variant_id")
            sku_from_variant = variant_to_sku.get(str(variant_id))
            sku_cmd = item.get("sku")
            sku_target = sku_from_variant or sku_cmd

            if not sku_target:
                items_unmatched += 1
                continue

            qty = item.get("quantity", 0) or 0

            if qty == 0:
                items_skipped_zero_qty += 1
                continue

            items_matched += 1

            # Récupération des montants
            item_gross_sales = float(item.get("gross_sales") or 0)
            item_discounts = float(item.get("discounts") or 0)
            item_refunds = float(item.get("refunds") or 0)
            item_net_sales = float(item.get("net_sales") or 0)

            # ✅ Détecter les variants supprimés et créer le mapping
            if sku_target not in inventory_by_sku and sku_target not in deleted_variants:
                product_id = item.get("product_id")
                
                # Récupérer les infos du produit ET variant via l'API
                product_info = get_product_info(product_id, variant_id)
                product_title = product_info["title"]
                vendor = product_info["vendor"]
                
                # ✅ Vérifier si ce produit existe déjà dans l'inventaire (doublon)
                matching_sku = None
                for inv_product in inventory:
                    if (inv_product.get("Marque") == vendor and 
                        inv_product.get("Produit") == product_title):
                        matching_sku = inv_product.get("SKU")
                        break
                
                if matching_sku:
                    # ✅ Doublon détecté : créer le mapping pour fusion
                    duplicate_sku_mapping[sku_target] = matching_sku
                    print(f"🔗 FUSION : {vendor} - {product_title}")
                    print(f"   Ancien SKU {sku_target} → Nouveau SKU {matching_sku}")
                else:
                    # ✅ Produit vraiment supprimé
                    print(f"🗑️ VARIANT SUPPRIMÉ : {vendor} - {product_title} (SKU: {sku_target})")
                    
                    deleted_variants[sku_target] = {
                        "Marque": vendor,
                        "Produit": product_title,
                        "SKU": sku_target,
                        "Variant ID": variant_id,
                        "Prix unitaire ($)": 0.0
                    }

            # ✅ FUSION : Si c'est un ancien SKU, rediriger vers le nouveau
            final_sku = duplicate_sku_mapping.get(sku_target, sku_target)

            if final_sku not in sales_data:
                sales_data[final_sku] = {
                    "V60": 0, "V120": 0, "V180": 0, "V365": 0,
                    "net_sales_v60": 0.0,
                    "net_sales_v120": 0.0,
                    "net_sales_v180": 0.0,
                    "net_sales_v365": 0.0,
                    "gross_sales": 0.0,
                    "discounts": 0.0,
                    "refunds": 0.0,
                    "net_sales": 0.0
                }

            # Périodes cumulatives
            if order_date >= cutoff_365:
                sales_data[final_sku]["V365"] += qty
                sales_data[final_sku]["net_sales_v365"] += item_net_sales
            if order_date >= cutoff_180:
                sales_data[final_sku]["V180"] += qty
                sales_data[final_sku]["net_sales_v180"] += item_net_sales
            if order_date >= cutoff_120:
                sales_data[final_sku]["V120"] += qty
                sales_data[final_sku]["net_sales_v120"] += item_net_sales
            if order_date >= cutoff_60:
                sales_data[final_sku]["V60"] += qty
                sales_data[final_sku]["net_sales_v60"] += item_net_sales

            # Agrégats financiers
            sales_data[final_sku]["gross_sales"] += item_gross_sales
            sales_data[final_sku]["discounts"] += item_discounts
            sales_data[final_sku]["refunds"] += item_refunds
            sales_data[final_sku]["net_sales"] += item_net_sales

    # RÉSUMÉ
    match_rate = (items_matched / items_processed * 100) if items_processed else 0
    print(f"\n📊 RÉSUMÉ GLOBAL:")
    print(f"   Items traités           : {items_processed}")
    print(f"   Items matchés           : {items_matched}")
    print(f"   Items non-matchés       : {items_unmatched}")
    print(f"   Items ignorés (qty=0)   : {items_skipped_zero_qty}")
    print(f"   SKUs avec ventes        : {len(sales_data)}")
    print(f"   🔗 Doublons fusionnés   : {len(duplicate_sku_mapping)}")
    print(f"   🗑️ Variants supprimés   : {len(deleted_variants)}")
    print(f"   Taux matching           : {match_rate:.1f}%\n")

    # Rapport final
    report = []
    
    # Produits actuels
    for p in inventory:
        sku = p.get("SKU")
        ventes = sales_data.get(sku, {
            "V60": 0, "V120": 0, "V180": 0, "V365": 0,
            "net_sales_v60": 0.0,
            "net_sales_v120": 0.0,
            "net_sales_v180": 0.0,
            "net_sales_v365": 0.0,
            "gross_sales": 0.0,
            "discounts": 0.0,
            "refunds": 0.0,
            "net_sales": 0.0
        })

        stock = p.get("Stock actuel") or 0
        stock = stock if stock > 0 else 0
        prix_unitaire = p.get("Prix unitaire ($)", 0)
        valeur_stock = stock * prix_unitaire

        report.append({
            "Marque": p.get("Marque"),
            "Produit": p.get("Produit"),
            "SKU": sku,
            "Variant ID": p.get("Variant ID"),
            "Stock": stock,
            "Prix unitaire ($)": prix_unitaire,
            "Valeur Stock ($)": round(valeur_stock, 2),
            "V60": ventes["V60"],
            "V120": ventes["V120"],
            "V180": ventes["V180"],
            "V365": ventes["V365"],
            "Montant V60 ($)": round(ventes["net_sales_v60"], 2),
            "Montant V120 ($)": round(ventes["net_sales_v120"], 2),
            "Montant V180 ($)": round(ventes["net_sales_v180"], 2),
            "Montant V365 ($)": round(ventes["net_sales_v365"], 2),
            "Gross Sales": round(ventes["gross_sales"], 2),
            "Discounts": round(ventes["discounts"], 2),
            "Refunds": round(ventes["refunds"], 2),
            "Net Sales": round(ventes["net_sales"], 2),
            "Suggestion (3m)": max(0, round(ventes["V180"] / 3 - stock, 2)),
            "Alerte": "✅ OK" if stock > 0 else "🚨 Rupture",
            "is_deleted": False
        })

    # ✅ Ajouter les variants VRAIMENT supprimés (pas les doublons)
    for sku, deleted_info in deleted_variants.items():
        ventes = sales_data.get(sku, {
            "V60": 0, "V120": 0, "V180": 0, "V365": 0,
            "net_sales_v60": 0.0,
            "net_sales_v120": 0.0,
            "net_sales_v180": 0.0,
            "net_sales_v365": 0.0,
            "gross_sales": 0.0,
            "discounts": 0.0,
            "refunds": 0.0,
            "net_sales": 0.0
        })

        report.append({
            "Marque": deleted_info["Marque"],
            "Produit": f"🗑️ {deleted_info['Produit']}",
            "SKU": sku,
            "Variant ID": deleted_info["Variant ID"],
            "Stock": 0,
            "Prix unitaire ($)": deleted_info["Prix unitaire ($)"],
            "Valeur Stock ($)": 0,
            "V60": ventes["V60"],
            "V120": ventes["V120"],
            "V180": ventes["V180"],
            "V365": ventes["V365"],
            "Montant V60 ($)": round(ventes["net_sales_v60"], 2),
            "Montant V120 ($)": round(ventes["net_sales_v120"], 2),
            "Montant V180 ($)": round(ventes["net_sales_v180"], 2),
            "Montant V365 ($)": round(ventes["net_sales_v365"], 2),
            "Gross Sales": round(ventes["gross_sales"], 2),
            "Discounts": round(ventes["discounts"], 2),
            "Refunds": round(ventes["refunds"], 2),
            "Net Sales": round(ventes["net_sales"], 2),
            "Suggestion (3m)": 0,
            "Alerte": "🗑️ SUPPRIMÉ",
            "is_deleted": True
        })

    # Regroupement par marque
    grouped = defaultdict(lambda: {
        "Marque": "",
        "Produits": [],
        "Totaux": {
            "Valeur Stock Total ($)": 0,
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
        grouped[brand]["Totaux"]["Montant V60 Total ($)"] += row["Montant V60 ($)"]
        grouped[brand]["Totaux"]["Montant V120 Total ($)"] += row["Montant V120 ($)"]
        grouped[brand]["Totaux"]["Montant V180 Total ($)"] += row["Montant V180 ($)"]
        grouped[brand]["Totaux"]["Montant V365 Total ($)"] += row["Montant V365 ($)"]

    for brand_data in grouped.values():
        for key in brand_data["Totaux"]:
            brand_data["Totaux"][key] = round(brand_data["Totaux"][key], 2)

    print(f"⏱ Rapport généré en {time.time() - start:.2f}s\n")
    return list(grouped.values())

@report_bp.route("/report")
def report():
    try:
        return jsonify(generate_report_data())
    except Exception as e:
        print(f"❌ ERREUR : {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# from flask import Blueprint, jsonify
# from datetime import datetime, timedelta
# from collections import defaultdict

# report_bp = Blueprint("report", __name__)

# # ✅ Cache pour éviter les appels API répétés
# product_cache = {}

# def get_product_info(product_id):
#     """Récupère les infos d'un produit (même supprimé) via l'API Shopify"""
#     if not product_id:
#         return {"title": "Produit inconnu", "vendor": "Marque inconnue"}
    
#     # Vérifier le cache
#     if product_id in product_cache:
#         return product_cache[product_id]
    
#     try:
#         from services.shopify_api import shopify_get
#         response = shopify_get(f"products/{product_id}.json")
        
#         if response and "product" in response:
#             p = response["product"]
#             info = {
#                 "title": p.get("title", "Produit inconnu"),
#                 "vendor": p.get("vendor", "Marque inconnue")
#             }
#             product_cache[product_id] = info
#             print(f"   ✅ Récupéré : {info['vendor']} - {info['title']}")
#             return info
#     except Exception as e:
#         print(f"   ⚠️ Erreur product_id {product_id}: {e}")
    
#     # Fallback
#     fallback = {"title": f"Produit {product_id}", "vendor": "Marque inconnue"}
#     product_cache[product_id] = fallback
#     return fallback

# def generate_report_data():
#     """
#     Rapport 100% compatible Shopify Analytics
#     - Net Items Sold (98% précision) ✅
#     - Net Sales par période (revenus réels) ✅
#     - Totaux par marque ✅
#     - Variants supprimés inclus ✅
#     """
#     import time
#     start = time.time()

#     from endpoints.inventory_endpoint import generate_inventory_data
#     from endpoints.orders_endpoint import generate_orders_data

#     inventory = generate_inventory_data()
#     orders = generate_orders_data().get("orders", [])

#     print(f"\n{'='*80}")
#     print(f"📦 INVENTAIRE : {len(inventory)} variantes")
#     print(f"📦 COMMANDES : {len(orders)}")
#     print(f"{'='*80}\n")

#     # Mapping
#     variant_to_sku = {}
#     inventory_by_sku = {}
    
#     for p in inventory:
#         vid = p.get("Variant ID")
#         sku = p.get("SKU")
#         if vid is not None:
#             variant_to_sku[str(vid)] = sku
#         if sku:
#             inventory_by_sku[sku] = p

#     print(f"🔑 Mapping : {len(variant_to_sku)} variant_id -> SKU")
#     print(f"🔍 SKUs inventaire : {len(inventory_by_sku)}\n")

#     # Périodes
#     now = datetime.utcnow()
#     cutoff_60  = (now - timedelta(days=60)).replace(hour=0, minute=0, second=0, microsecond=0)
#     cutoff_120 = (now - timedelta(days=120)).replace(hour=0, minute=0, second=0, microsecond=0)
#     cutoff_180 = (now - timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)
#     cutoff_365 = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)

#     print(f"📅 PÉRIODES (UTC, startOfDay comme Shopify):")
#     print(f"   Aujourd'hui : {now.strftime('%Y-%m-%d %H:%M:%S')}")
#     print(f"   Cutoff 365j : {cutoff_365.strftime('%Y-%m-%d %H:%M:%S')}\n")

#     # Stockage
#     sales_data = {}
#     items_processed = 0
#     items_matched = 0
#     items_unmatched = 0
#     items_skipped_zero_qty = 0

#     # ✅ Stockage des variants supprimés
#     deleted_variants = {}

#     # TRAITEMENT
#     for order in orders:
#         created = order.get("created_at")
#         if not created:
#             continue

#         try:
#             order_date = datetime.strptime(created[:19], "%Y-%m-%dT%H:%M:%S")
#         except:
#             continue

#         for item in order.get("line_items", []):
#             items_processed += 1

#             variant_id = item.get("variant_id")
#             sku_from_variant = variant_to_sku.get(str(variant_id))
#             sku_cmd = item.get("sku")
#             sku_target = sku_from_variant or sku_cmd

#             if not sku_target:
#                 items_unmatched += 1
#                 continue

#             qty = item.get("quantity", 0) or 0

#             if qty == 0:
#                 items_skipped_zero_qty += 1
#                 continue

#             items_matched += 1

#             # Récupération des montants
#             item_gross_sales = float(item.get("gross_sales") or 0)
#             item_discounts = float(item.get("discounts") or 0)
#             item_refunds = float(item.get("refunds") or 0)
#             item_net_sales = float(item.get("net_sales") or 0)

#             if sku_target not in sales_data:
#                 sales_data[sku_target] = {
#                     "V60": 0, "V120": 0, "V180": 0, "V365": 0,
#                     "net_sales_v60": 0.0,
#                     "net_sales_v120": 0.0,
#                     "net_sales_v180": 0.0,
#                     "net_sales_v365": 0.0,
#                     "gross_sales": 0.0,
#                     "discounts": 0.0,
#                     "refunds": 0.0,
#                     "net_sales": 0.0
#                 }

#             # Périodes cumulatives
#             if order_date >= cutoff_365:
#                 sales_data[sku_target]["V365"] += qty
#                 sales_data[sku_target]["net_sales_v365"] += item_net_sales
#             if order_date >= cutoff_180:
#                 sales_data[sku_target]["V180"] += qty
#                 sales_data[sku_target]["net_sales_v180"] += item_net_sales
#             if order_date >= cutoff_120:
#                 sales_data[sku_target]["V120"] += qty
#                 sales_data[sku_target]["net_sales_v120"] += item_net_sales
#             if order_date >= cutoff_60:
#                 sales_data[sku_target]["V60"] += qty
#                 sales_data[sku_target]["net_sales_v60"] += item_net_sales

#             # Agrégats financiers
#             sales_data[sku_target]["gross_sales"] += item_gross_sales
#             sales_data[sku_target]["discounts"] += item_discounts
#             sales_data[sku_target]["refunds"] += item_refunds
#             sales_data[sku_target]["net_sales"] += item_net_sales

#             # ✅ NOUVEAU : Détecter les variants supprimés
#             if sku_target not in inventory_by_sku and sku_target not in deleted_variants:
#                 product_id = item.get("product_id")
                
#                 # Récupérer les infos du produit via l'API
#                 product_info = get_product_info(product_id)
#                 product_title = product_info["title"]
#                 vendor = product_info["vendor"]
                
#                 print(f"🗑️ VARIANT SUPPRIMÉ : {vendor} - {product_title} (SKU: {sku_target})")
                
#                 deleted_variants[sku_target] = {
#                     "Marque": vendor,
#                     "Produit": product_title,
#                     "SKU": sku_target,
#                     "Variant ID": variant_id,
#                     "Prix unitaire ($)": float(item.get("price") or 0) if "price" in item else 0.0
#                 }

#     # RÉSUMÉ
#     match_rate = (items_matched / items_processed * 100) if items_processed else 0
#     print(f"\n📊 RÉSUMÉ GLOBAL:")
#     print(f"   Items traités           : {items_processed}")
#     print(f"   Items matchés           : {items_matched}")
#     print(f"   Items non-matchés       : {items_unmatched}")
#     print(f"   Items ignorés (qty=0)   : {items_skipped_zero_qty}")
#     print(f"   SKUs avec ventes        : {len(sales_data)}")
#     print(f"   🗑️ Variants supprimés   : {len(deleted_variants)}")
#     print(f"   Taux matching           : {match_rate:.1f}%\n")

#     # Rapport final
#     report = []
    
#     # Produits actuels
#     for p in inventory:
#         sku = p.get("SKU")
#         ventes = sales_data.get(sku, {
#             "V60": 0, "V120": 0, "V180": 0, "V365": 0,
#             "net_sales_v60": 0.0,
#             "net_sales_v120": 0.0,
#             "net_sales_v180": 0.0,
#             "net_sales_v365": 0.0,
#             "gross_sales": 0.0,
#             "discounts": 0.0,
#             "refunds": 0.0,
#             "net_sales": 0.0
#         })

#         stock = p.get("Stock actuel") or 0
#         stock = stock if stock > 0 else 0
#         prix_unitaire = p.get("Prix unitaire ($)", 0)
#         valeur_stock = stock * prix_unitaire

#         report.append({
#             "Marque": p.get("Marque"),
#             "Produit": p.get("Produit"),
#             "SKU": sku,
#             "Variant ID": p.get("Variant ID"),
#             "Stock": stock,
#             "Prix unitaire ($)": prix_unitaire,
#             "Valeur Stock ($)": round(valeur_stock, 2),
#             "V60": ventes["V60"],
#             "V120": ventes["V120"],
#             "V180": ventes["V180"],
#             "V365": ventes["V365"],
#             "Montant V60 ($)": round(ventes["net_sales_v60"], 2),
#             "Montant V120 ($)": round(ventes["net_sales_v120"], 2),
#             "Montant V180 ($)": round(ventes["net_sales_v180"], 2),
#             "Montant V365 ($)": round(ventes["net_sales_v365"], 2),
#             "Gross Sales": round(ventes["gross_sales"], 2),
#             "Discounts": round(ventes["discounts"], 2),
#             "Refunds": round(ventes["refunds"], 2),
#             "Net Sales": round(ventes["net_sales"], 2),
#             "Suggestion (3m)": max(0, round(ventes["V180"] / 3 - stock, 2)),
#             "Alerte": "✅ OK" if stock > 0 else "🚨 Rupture",
#             "is_deleted": False
#         })

#     # ✅ Ajouter les variants supprimés
#     for sku, deleted_info in deleted_variants.items():
#         ventes = sales_data.get(sku, {
#             "V60": 0, "V120": 0, "V180": 0, "V365": 0,
#             "net_sales_v60": 0.0,
#             "net_sales_v120": 0.0,
#             "net_sales_v180": 0.0,
#             "net_sales_v365": 0.0,
#             "gross_sales": 0.0,
#             "discounts": 0.0,
#             "refunds": 0.0,
#             "net_sales": 0.0
#         })

#         report.append({
#             "Marque": deleted_info["Marque"],
#             "Produit": f"🗑️ {deleted_info['Produit']}",
#             "SKU": sku,
#             "Variant ID": deleted_info["Variant ID"],
#             "Stock": 0,
#             "Prix unitaire ($)": deleted_info["Prix unitaire ($)"],
#             "Valeur Stock ($)": 0,
#             "V60": ventes["V60"],
#             "V120": ventes["V120"],
#             "V180": ventes["V180"],
#             "V365": ventes["V365"],
#             "Montant V60 ($)": round(ventes["net_sales_v60"], 2),
#             "Montant V120 ($)": round(ventes["net_sales_v120"], 2),
#             "Montant V180 ($)": round(ventes["net_sales_v180"], 2),
#             "Montant V365 ($)": round(ventes["net_sales_v365"], 2),
#             "Gross Sales": round(ventes["gross_sales"], 2),
#             "Discounts": round(ventes["discounts"], 2),
#             "Refunds": round(ventes["refunds"], 2),
#             "Net Sales": round(ventes["net_sales"], 2),
#             "Suggestion (3m)": 0,
#             "Alerte": "🗑️ SUPPRIMÉ",
#             "is_deleted": True
#         })

#     # Regroupement par marque
#     grouped = defaultdict(lambda: {
#         "Marque": "",
#         "Produits": [],
#         "Totaux": {
#             "Valeur Stock Total ($)": 0,
#             "Montant V60 Total ($)": 0,
#             "Montant V120 Total ($)": 0,
#             "Montant V180 Total ($)": 0,
#             "Montant V365 Total ($)": 0
#         }
#     })
    
#     for row in report:
#         brand = row.get("Marque") or "Inconnue"
#         grouped[brand]["Marque"] = brand
#         grouped[brand]["Produits"].append(row)
#         grouped[brand]["Totaux"]["Valeur Stock Total ($)"] += row["Valeur Stock ($)"]
#         grouped[brand]["Totaux"]["Montant V60 Total ($)"] += row["Montant V60 ($)"]
#         grouped[brand]["Totaux"]["Montant V120 Total ($)"] += row["Montant V120 ($)"]
#         grouped[brand]["Totaux"]["Montant V180 Total ($)"] += row["Montant V180 ($)"]
#         grouped[brand]["Totaux"]["Montant V365 Total ($)"] += row["Montant V365 ($)"]

#     for brand_data in grouped.values():
#         for key in brand_data["Totaux"]:
#             brand_data["Totaux"][key] = round(brand_data["Totaux"][key], 2)

#     print(f"⏱ Rapport généré en {time.time() - start:.2f}s\n")
#     return list(grouped.values())

# @report_bp.route("/report")
# def report():
#     try:
#         return jsonify(generate_report_data())
#     except Exception as e:
#         print(f"❌ ERREUR : {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

# # from flask import Blueprint, jsonify
# # from datetime import datetime, timedelta
# # from collections import defaultdict

# # report_bp = Blueprint("report", __name__)

# # def generate_report_data():
# #     """
# #     Rapport 100% compatible Shopify Analytics
# #     - Net Items Sold (98% précision) ✅
# #     - Net Sales par période (revenus réels) ✅
# #     - Totaux par marque ✅
# #     """
# #     import time
# #     start = time.time()

# #     from endpoints.inventory_endpoint import generate_inventory_data
# #     from endpoints.orders_endpoint import generate_orders_data

# #     inventory = generate_inventory_data()
# #     orders = generate_orders_data().get("orders", [])

# #     print(f"\n{'='*80}")
# #     print(f"📦 INVENTAIRE : {len(inventory)} variantes")
# #     print(f"📦 COMMANDES : {len(orders)}")
# #     print(f"{'='*80}\n")

# #     # Mapping
# #     variant_to_sku = {}
# #     inventory_by_sku = {}
    
# #     for p in inventory:
# #         vid = p.get("Variant ID")
# #         sku = p.get("SKU")
# #         if vid is not None:
# #             variant_to_sku[str(vid)] = sku
# #         if sku:
# #             inventory_by_sku[sku] = p

# #     print(f"🔑 Mapping : {len(variant_to_sku)} variant_id -> SKU")
# #     print(f"🔍 SKUs inventaire : {len(inventory_by_sku)}\n")

# #     # ✅ PÉRIODES COMME SHOPIFY (startOfDay)
# #     now = datetime.utcnow()
# #     cutoff_60  = (now - timedelta(days=60)).replace(hour=0, minute=0, second=0, microsecond=0)
# #     cutoff_120 = (now - timedelta(days=120)).replace(hour=0, minute=0, second=0, microsecond=0)
# #     cutoff_180 = (now - timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)
# #     cutoff_365 = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)

# #     print(f"📅 PÉRIODES (UTC, startOfDay comme Shopify):")
# #     print(f"   Aujourd'hui : {now.strftime('%Y-%m-%d %H:%M:%S')}")
# #     print(f"   Cutoff 365j : {cutoff_365.strftime('%Y-%m-%d %H:%M:%S')}\n")

# #     # Stockage
# #     sales_data = {}
# #     items_processed = 0
# #     items_matched = 0
# #     items_unmatched = 0
# #     items_skipped_zero_qty = 0

# #     # TRAITEMENT
# #     for order in orders:
# #         created = order.get("created_at")
# #         if not created:
# #             continue

# #         try:
# #             order_date = datetime.strptime(created[:19], "%Y-%m-%dT%H:%M:%S")
# #         except:
# #             continue

# #         for item in order.get("line_items", []):
# #             items_processed += 1

# #             variant_id = item.get("variant_id")
# #             sku_from_variant = variant_to_sku.get(str(variant_id))
# #             sku_cmd = item.get("sku")
# #             sku_target = sku_from_variant or (sku_cmd if sku_cmd in inventory_by_sku else None)

# #             if not sku_target:
# #                 items_unmatched += 1
# #                 continue

# #             qty = item.get("quantity", 0) or 0

# #             # ✅ IGNORE les items avec qty=0 (remboursements complets)
# #             if qty == 0:
# #                 items_skipped_zero_qty += 1
# #                 continue

# #             items_matched += 1

# #             # ✅ RÉCUPÉRATION DES MONTANTS
# #             item_gross_sales = float(item.get("gross_sales") or 0)
# #             item_discounts = float(item.get("discounts") or 0)
# #             item_refunds = float(item.get("refunds") or 0)
# #             item_net_sales = float(item.get("net_sales") or 0)

# #             if sku_target not in sales_data:
# #                 sales_data[sku_target] = {
# #                     "V60": 0, "V120": 0, "V180": 0, "V365": 0,
# #                     # ✅ NET SALES PAR PÉRIODE
# #                     "net_sales_v60": 0.0,
# #                     "net_sales_v120": 0.0,
# #                     "net_sales_v180": 0.0,
# #                     "net_sales_v365": 0.0,
# #                     "gross_sales": 0.0,
# #                     "discounts": 0.0,
# #                     "refunds": 0.0,
# #                     "net_sales": 0.0
# #                 }

# #             # PÉRIODES CUMULATIVES (quantités)
# #             if order_date >= cutoff_365:
# #                 sales_data[sku_target]["V365"] += qty
# #                 sales_data[sku_target]["net_sales_v365"] += item_net_sales  # ✅
# #             if order_date >= cutoff_180:
# #                 sales_data[sku_target]["V180"] += qty
# #                 sales_data[sku_target]["net_sales_v180"] += item_net_sales  # ✅
# #             if order_date >= cutoff_120:
# #                 sales_data[sku_target]["V120"] += qty
# #                 sales_data[sku_target]["net_sales_v120"] += item_net_sales  # ✅
# #             if order_date >= cutoff_60:
# #                 sales_data[sku_target]["V60"] += qty
# #                 sales_data[sku_target]["net_sales_v60"] += item_net_sales  # ✅

# #             # Agrégats financiers globaux
# #             sales_data[sku_target]["gross_sales"] += item_gross_sales
# #             sales_data[sku_target]["discounts"] += item_discounts
# #             sales_data[sku_target]["refunds"] += item_refunds
# #             sales_data[sku_target]["net_sales"] += item_net_sales

# #     # RÉSUMÉ
# #     match_rate = (items_matched / items_processed * 100) if items_processed else 0
# #     print(f"📊 RÉSUMÉ GLOBAL:")
# #     print(f"   Items traités           : {items_processed}")
# #     print(f"   Items matchés           : {items_matched}")
# #     print(f"   Items non-matchés       : {items_unmatched}")
# #     print(f"   Items ignorés (qty=0)   : {items_skipped_zero_qty}")
# #     print(f"   SKUs avec ventes        : {len(sales_data)}")
# #     print(f"   Taux matching           : {match_rate:.1f}%\n")

# #     # Rapport final
# #     report = []
# #     for p in inventory:
# #         sku = p.get("SKU")
# #         ventes = sales_data.get(sku, {
# #             "V60": 0, "V120": 0, "V180": 0, "V365": 0,
# #             "net_sales_v60": 0.0,
# #             "net_sales_v120": 0.0,
# #             "net_sales_v180": 0.0,
# #             "net_sales_v365": 0.0,
# #             "gross_sales": 0.0,
# #             "discounts": 0.0,
# #             "refunds": 0.0,
# #             "net_sales": 0.0
# #         })

# #         stock = p.get("Stock actuel") or 0
# #         stock = stock if stock > 0 else 0
# #         prix_unitaire = p.get("Prix unitaire ($)", 0)

# #         # ✅ VALEUR DU STOCK
# #         valeur_stock = stock * prix_unitaire

# #         report.append({
# #             "Marque": p.get("Marque"),
# #             "Produit": p.get("Produit"),
# #             "SKU": sku,
# #             "Variant ID": p.get("Variant ID"),
# #             "Stock": stock,
# #             "Prix unitaire ($)": prix_unitaire,
# #             "Valeur Stock ($)": round(valeur_stock, 2),  # ✅
# #             "V60": ventes["V60"],
# #             "V120": ventes["V120"],
# #             "V180": ventes["V180"],
# #             "V365": ventes["V365"],
# #             # ✅ NET SALES PAR PÉRIODE (revenus réels)
# #             "Montant V60 ($)": round(ventes["net_sales_v60"], 2),
# #             "Montant V120 ($)": round(ventes["net_sales_v120"], 2),
# #             "Montant V180 ($)": round(ventes["net_sales_v180"], 2),
# #             "Montant V365 ($)": round(ventes["net_sales_v365"], 2),
# #             "Gross Sales": round(ventes["gross_sales"], 2),
# #             "Discounts": round(ventes["discounts"], 2),
# #             "Refunds": round(ventes["refunds"], 2),
# #             "Net Sales": round(ventes["net_sales"], 2),
# #             "Suggestion (3m)": max(0, round(ventes["V180"] / 3 - stock, 2)),
# #             "Alerte": "✅ OK" if stock > 0 else "🚨 Rupture"
# #         })

# #     # ✅ REGROUPEMENT PAR MARQUE AVEC TOTAUX
# #     grouped = defaultdict(lambda: {
# #         "Marque": "",
# #         "Produits": [],
# #         "Totaux": {
# #             "Valeur Stock Total ($)": 0,
# #             "Montant V60 Total ($)": 0,
# #             "Montant V120 Total ($)": 0,
# #             "Montant V180 Total ($)": 0,
# #             "Montant V365 Total ($)": 0
# #         }
# #     })
    
# #     for row in report:
# #         brand = row.get("Marque") or "Inconnue"
# #         grouped[brand]["Marque"] = brand
# #         grouped[brand]["Produits"].append(row)
        
# #         # ✅ CUMUL DES TOTAUX PAR MARQUE
# #         grouped[brand]["Totaux"]["Valeur Stock Total ($)"] += row["Valeur Stock ($)"]
# #         grouped[brand]["Totaux"]["Montant V60 Total ($)"] += row["Montant V60 ($)"]
# #         grouped[brand]["Totaux"]["Montant V120 Total ($)"] += row["Montant V120 ($)"]
# #         grouped[brand]["Totaux"]["Montant V180 Total ($)"] += row["Montant V180 ($)"]
# #         grouped[brand]["Totaux"]["Montant V365 Total ($)"] += row["Montant V365 ($)"]

# #     # Arrondir les totaux
# #     for brand_data in grouped.values():
# #         for key in brand_data["Totaux"]:
# #             brand_data["Totaux"][key] = round(brand_data["Totaux"][key], 2)

# #     print(f"⏱ Rapport généré en {time.time() - start:.2f}s\n")
# #     return list(grouped.values())

# # @report_bp.route("/report")
# # def report():
# #     try:
# #         return jsonify(generate_report_data())
# #     except Exception as e:
# #         print(f"❌ ERREUR : {e}")
# #         import traceback
# #         traceback.print_exc()
# #         return jsonify({"error": str(e)}), 500

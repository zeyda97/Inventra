from flask import Blueprint, jsonify
from services.shopify_api import shopify_get_all
import requests
import os

inventory_bp = Blueprint("inventory", __name__)

# === 📊 Fonctions de génération des données (sans HTTP) ===

def shopify_graphql(query):
    """
    Exécute une requête GraphQL sur l'API Shopify Admin
    """
    # ✅ Utiliser vos variables d'environnement
    shop_domain = os.getenv("MY_SHOPIFY_DOMAIN")  # h-parfums.myshopify.com
    access_token = os.getenv("ACCESS_TOKEN")
    
    url = f"https://{shop_domain}/admin/api/2024-10/graphql.json"
    
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }
    
    response = requests.post(url, json={"query": query}, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"GraphQL Error {response.status_code}: {response.text}")


def get_inventory_items_costs(inventory_item_ids):
    """
    Récupère les coûts via GraphQL (plus fiable que REST)
    Shopify GraphQL permet de récupérer unitCost de manière fiable
    """
    if not inventory_item_ids:
        return {}
    
    costs = {}
    
    # GraphQL peut gérer ~50 requêtes par batch (limite de complexité)
    batch_size = 50
    
    for i in range(0, len(inventory_item_ids), batch_size):
        batch_ids = inventory_item_ids[i:i + batch_size]
        
        print(f"📡 GraphQL Batch {i//batch_size + 1}: {len(batch_ids)} IDs demandés")
        
        # Construire les alias pour chaque inventory item
        queries = []
        for idx, inv_id in enumerate(batch_ids):
            gid = f"gid://shopify/InventoryItem/{inv_id}"
            queries.append(f'item{idx}: inventoryItem(id: "{gid}") {{ id unitCost {{ amount currencyCode }} }}')
        
        query = f"query {{ {' '.join(queries)} }}"
        
        try:
            response = shopify_graphql(query)
            
            if response and 'data' in response:
                items_found = 0
                costs_found = 0
                
                for key, item_data in response['data'].items():
                    if item_data:
                        items_found += 1
                        # Extraire l'ID numérique du GID
                        gid = item_data.get('id', '')
                        numeric_id = gid.split('/')[-1]
                        
                        unit_cost = item_data.get('unitCost')
                        if unit_cost and unit_cost.get('amount'):
                            amount = unit_cost['amount']
                            costs[numeric_id] = float(amount)
                            costs_found += 1
                            
                            # Log des coûts non-nuls
                            if float(amount) > 0:
                                print(f"  💰 inventory_item_id {numeric_id}: coût = {amount} {unit_cost.get('currencyCode', 'CAD')}")
                        else:
                            costs[numeric_id] = 0.0
                
                print(f"✅ Batch traité: {items_found} items trouvés, {costs_found} coûts récupérés")
                
            if 'errors' in response and response['errors']:
                print(f"⚠️ Erreurs GraphQL: {response['errors']}")
                
        except Exception as e:
            print(f"⚠️ Erreur GraphQL batch {i//batch_size + 1}: {e}")
    
    print(f"\n📊 Total coûts récupérés: {len(costs)}, dont {sum(1 for c in costs.values() if c > 0)} non-nuls\n")
    return costs


def generate_inventory_data():
    """
    ✅ Version simplifiée et fiable de l'inventaire pour Shopify Prestige.
    Récupère toutes les variantes de produits avec :
    - Marque
    - Produit (titre + variante)
    - SKU
    - Variant ID (identifiant unique)
    - Stock actuel
    - Prix unitaire (prix de VENTE)
    - Coût par article (coût d'ACHAT) via GraphQL
    """
    try:
        products = shopify_get_all("products.json", {"limit": 250}, root_key="products")
    except Exception as e:
        raise Exception(f"Erreur de connexion à Shopify : {e}")

    # ✅ ÉTAPE 1 : Collecter tous les inventory_item_ids
    inventory_item_ids = []
    debug_14juillet = {}  # Pour tracer "14 Juillet 100 ml"
    
    for p in products:
        for v in p.get("variants", []):
            inv_item_id = v.get("inventory_item_id")
            if inv_item_id:
                inventory_item_ids.append(inv_item_id)
                
                # ✅ DIAGNOSTIC : Capturer "14 Juillet 100 ml"
                if "14 Juillet" in p.get("title", "") and "100 ml" in v.get("title", ""):
                    debug_14juillet = {
                        "product_title": p.get("title"),
                        "variant_title": v.get("title"),
                        "variant_id": v.get("id"),
                        "inventory_item_id": inv_item_id,
                        "sku": v.get("sku"),
                        "price": v.get("price")
                    }
                    print(f"\n🔍 TROUVÉ: 14 Juillet 100 ml")
                    print(f"   Product: {debug_14juillet['product_title']}")
                    print(f"   Variant: {debug_14juillet['variant_title']}")
                    print(f"   Variant ID: {debug_14juillet['variant_id']}")
                    print(f"   Inventory Item ID: {debug_14juillet['inventory_item_id']}")
                    print(f"   SKU: {debug_14juillet['sku']}")
                    print(f"   Prix: {debug_14juillet['price']} $\n")
    
    print(f"📦 Récupération des coûts via GraphQL pour {len(inventory_item_ids)} variants...")
    
    # ✅ ÉTAPE 2 : Récupérer tous les coûts via GraphQL
    costs = get_inventory_items_costs(inventory_item_ids)
    
    # ✅ DIAGNOSTIC : Vérifier si le coût de "14 Juillet 100 ml" a été récupéré
    if debug_14juillet:
        inv_item_id_str = str(debug_14juillet['inventory_item_id'])
        cost_retrieved = costs.get(inv_item_id_str, 0.0)
        print(f"\n🔍 VÉRIFICATION: 14 Juillet 100 ml")
        print(f"   Inventory Item ID recherché: {inv_item_id_str}")
        print(f"   Coût récupéré: {cost_retrieved} $")
        if cost_retrieved == 0.0:
            print(f"   ❌ PROBLÈME: Le coût n'a pas été récupéré ou est à 0 dans Shopify!")
            print(f"   🔧 Vérifiez dans Shopify Admin → Produits → 14 Juillet → Variant 100 ml → 'Cost per item'\n")
        else:
            print(f"   ✅ Coût correctement récupéré via GraphQL!\n")
    
    print(f"✅ Coûts récupérés : {len(costs)} items\n")

    # ✅ ÉTAPE 3 : Construire les données d'inventaire
    rows = []
    for p in products:
        brand = p.get("vendor", "Inconnue")
        title = p.get("title", "").strip()

        for v in p.get("variants", []):
            inv_item_id = str(v.get("inventory_item_id", ""))
            cost = costs.get(inv_item_id, 0.0)
            
            rows.append({
                "Marque": brand,
                "Produit": f"{title} {v.get('title') or ''}".strip(),
                "SKU": v.get("sku"),
                "Variant ID": str(v.get("id")),
                "Stock actuel": v.get("inventory_quantity", 0),
                "Prix unitaire ($)": float(v.get("price") or 0),      # Prix de VENTE
                "Coût par article ($)": cost                          # ✅ Coût d'ACHAT via GraphQL
            })

    return rows


def generate_inventory_grouped_data():
    """
    ✅ Version groupée de l'inventaire par SKU.
    Fournit un résumé : stock total, prix, coût, marque et produit.
    """
    try:
        products = shopify_get_all("products.json", {"limit": 250}, root_key="products")
    except Exception as e:
        raise Exception(f"Erreur de connexion à Shopify : {e}")

    # ✅ Récupérer les coûts via GraphQL
    inventory_item_ids = []
    for p in products:
        for v in p.get("variants", []):
            inv_item_id = v.get("inventory_item_id")
            if inv_item_id:
                inventory_item_ids.append(inv_item_id)
    
    costs = get_inventory_items_costs(inventory_item_ids)

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
            inv_item_id = str(v.get("inventory_item_id", ""))
            cost = costs.get(inv_item_id, 0.0)

            if sku not in grouped:
                grouped[sku] = {
                    "Marque": brand,
                    "Produit": f"{title} {v.get('title') or ''}".strip(),
                    "Prix unitaire ($)": price,
                    "Coût par article ($)": cost,
                    "Stock total": stock
                }
            else:
                grouped[sku]["Stock total"] += stock

    return [{"SKU": sku, **vals} for sku, vals in grouped.items()]


# === 🌐 Endpoints HTTP (minces wrappers) ===

@inventory_bp.route("/inventory/enriched")
def inventory_enriched_for_report():
    """Endpoint HTTP pour l'inventaire enrichi"""
    try:
        data = generate_inventory_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Erreur de génération de l'inventaire : {e}"}), 500


@inventory_bp.route("/data/inventory")
def get_inventory_grouped():
    """Endpoint HTTP pour l'inventaire groupé"""
    try:
        data = generate_inventory_grouped_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Erreur de génération de l'inventaire groupé : {e}"}), 500
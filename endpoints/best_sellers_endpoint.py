from flask import Blueprint, jsonify
from datetime import datetime, timedelta
from collections import defaultdict
from dateutil import parser
import pytz
from endpoints.orders_endpoint import generate_orders_data
from endpoints.orders_endpoint import shopify_graphql

best_sellers_bp = Blueprint("best_sellers_bp", __name__)

EXCLUDED_VARIANTS = ['2 ml', '1 ml sample', '1.5 ml sample', '10 ml', '15 ml']
EXCLUDED_PRODUCTS = ['Gift Card H Parfums']  # 🎁 Nom exact du produit



def generate_best_sellers_from_orders(orders_data, days):
    """
    Best-sellers aligné Shopify Analytics
    Utilise product_id + variant_id comme clé unique
    Exclut les échantillons et les cartes-cadeaux
    """
    shop_tz = pytz.timezone("America/Montreal")
    now = datetime.now(shop_tz)
    
    # startOfDay(-Xd)
    since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    
    # Clé = (product_id, variant_id)
    sales = defaultdict(int)
    product_info = {}
    
    for order in orders_data.get("orders", []):
        created_at = parser.isoparse(order["created_at"]).astimezone(shop_tz)
        
        # Filtre période
        if created_at < since:
            continue
        
        for li in order.get("line_items", []):
            # line_type = 'product'
            product_id = li.get("product_id")
            if not product_id:
                continue
            
            product_title = li.get("product_title") or ""
            variant_title = li.get("variant_title") or "Default Title"
            
            # ⛔ Exclusion des cartes-cadeaux (nom exact)
            if product_title == "Gift Card H Parfums":
                continue
            
            # ⛔ Exclusion des échantillons
            if any(term in variant_title for term in EXCLUDED_VARIANTS):
                continue
            
            # Quantité
            qty = li.get("quantity", 0)
            if qty <= 0:
                continue
            
            variant_id = li.get("variant_id")
            
            # Clé unique
            key = (product_id, variant_id)
            sales[key] += qty
            
            # Stocker les infos
            if key not in product_info:
                product_info[key] = {
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "product_title": product_title,
                    "variant_title": variant_title,
                    "sku": li.get("sku") or ""
                }
    
    # Format final
    result = []
    for (product_id, variant_id), qty in sales.items():
        info = product_info.get((product_id, variant_id), {})
        result.append({
            "product_id": str(product_id),
            "variant_id": str(variant_id),
            "product_title": info.get("product_title", ""),
            "variant_title": info.get("variant_title", ""),
            "sku": info.get("sku", ""),
            "net_items_sold": qty
        })
    
    # ORDER BY net_items_sold DESC
    result.sort(key=lambda x: x["net_items_sold"], reverse=True)
    
    return result[:1000]
def compute_best_sellers(top_30, top_120, top_n=40):
    """
    Détermine les best-sellers à partir des ventes 30j et 120j
    Clé unique = (product_id, variant_id)
    """

    # Index S120
    s120_index = {
        (i["product_id"], i["variant_id"]): i["net_items_sold"]
        for i in top_120
    }

    scored_items = []

    for item in top_30:
        key = (item["product_id"], item["variant_id"])

        s30 = item["net_items_sold"]
        s120 = s120_index.get(key, 0)

        # On ignore les produits sans historique minimal
        if s120 < 4:
            continue

        # Normalisation 120j -> base 30j
        normalized_120 = s120 / 4

        # Score hybride stabilité / momentum
        score = (0.6 * s30) + (0.4 * normalized_120)

        scored_items.append({
            **item,
            "rank_30": item.get("rank_30"),  # on garde ta variable
            "s30": s30,
            "s120": s120,
            "score": score  # interne uniquement
        })

    # Tri par score
    scored_items.sort(key=lambda x: x["score"], reverse=True)

    best_sellers = []

    for rank, item in enumerate(scored_items[:top_n], start=1):
        best_sellers.append({
            **item,
            "rank_30": rank,
            "s30": item["s30"],
            "s120": item["s120"],
            "is_best_seller": True
        })

    return best_sellers
# def compute_best_sellers(top_30, top_120, top_n=30):
#     """
#     Détermine les best-sellers à partir des ventes 30j et 120j
#     Clé unique = (product_id, variant_id)
#     """

#     # Index S120
#     s120_index = {
#         (i["product_id"], i["variant_id"]): i["net_items_sold"]
#         for i in top_120
#     }

#     best_sellers = []

#     for rank, item in enumerate(top_30[:top_n], start=1):
#         key = (item["product_id"], item["variant_id"])

#         s30 = item["net_items_sold"]
#         s120 = s120_index.get(key, 0)

#         # RÈGLE MÉTIER
#         if s120 >= max(2, 0.5 * s30):
#             best_sellers.append({
#                 **item,
#                 "rank_30": rank,
#                 "s30": s30,
#                 "s120": s120,
#                 "is_best_seller": True
#             })

#     return best_sellers


@best_sellers_bp.route("/data/best_sellers")
def get_best_sellers():
    try:
        orders_data = generate_orders_data()
        last_120 = generate_best_sellers_from_orders(orders_data, 120)
        last_30 = generate_best_sellers_from_orders(orders_data, 30)

        best_sellers = compute_best_sellers(last_30, last_120, top_n=30)
        
        return jsonify({
            "generated_at": datetime.utcnow().isoformat(),
            "last_120_days": last_120,
            "last_30_days": last_30,
            "best_sellers": best_sellers
            
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@best_sellers_bp.route("/sync/best_sellers_to_shopify")
def sync_best_sellers_to_shopify():
    try:
        orders_data = generate_orders_data()

        top_120 = generate_best_sellers_from_orders(orders_data, 120)
        top_30 = generate_best_sellers_from_orders(orders_data, 30)

        best_sellers = compute_best_sellers(top_30, top_120, top_n=30)

        # 🔥 Sync Shopify ici
        for item in best_sellers:

            variant_gid = f"gid://shopify/ProductVariant/{item['variant_id']}"

            update_variant_metafields(
                variant_gid=variant_gid,
                s30=item["s30"],
                s120=item["s120"],
                rank=item["rank_30"],
                is_best=True
            )

        return jsonify({"status": "sync complete", "count": len(best_sellers)})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
def update_variant_metafields(variant_gid, s30, s120, rank, is_best):
    """
    Met à jour les 4 metafields analytics d'une variante
    SANS spécifier le type (pour utiliser les définitions existantes)
    """
    mutation = f"""
    mutation {{
      metafieldsSet(metafields: [
        {{
          ownerId: "{variant_gid}",
          namespace: "analytics",
          key: "sales_30d",
          value: "{s30}"
        }},
        {{
          ownerId: "{variant_gid}",
          namespace: "analytics",
          key: "sales_120d",
          value: "{s120}"
        }},
        {{
          ownerId: "{variant_gid}",
          namespace: "analytics",
          key: "rank_30d",
          value: "{rank}"
        }},
        {{
          ownerId: "{variant_gid}",
          namespace: "analytics",
          key: "is_best_seller",
          value: "{'true' if is_best else 'false'}"
        }}
      ]) {{
        metafields {{
          id
          key
          value
        }}
        userErrors {{
          field
          message
        }}
      }}
    }}
    """

    result = shopify_graphql(mutation)
    
    if result and "data" in result:
        user_errors = result["data"]["metafieldsSet"]["userErrors"]
        if user_errors:
            print(f"⚠️  Erreur pour {variant_gid}: {user_errors}")
            return False
        else:
            print(f"✅ Metafields mis à jour pour {variant_gid}")
            return True
    else:
        print(f"❌ Échec GraphQL pour {variant_gid}")
        return False

def run_full_best_seller_sync():
    """
    Synchronisation complète basée sur les données de l'endpoint
    Vérifie top 120 ET top 30
    """
    try:
        print("🚀 Début de la synchronisation complète...")
        
        orders_data = generate_orders_data()
        top_120 = generate_best_sellers_from_orders(orders_data, 120)
        top_30 = generate_best_sellers_from_orders(orders_data, 30)

        best_sellers = compute_best_sellers(top_30, top_120, top_n=30)
        current_best_ids = {item["variant_id"] for item in best_sellers}

        print(f"📊 {len(best_sellers)} best-sellers actuels identifiés")

        # 1️⃣ Mettre à jour les best-sellers actuels (is_best_seller = true)
        success_count = 0
        for item in best_sellers:
            variant_gid = f"gid://shopify/ProductVariant/{item['variant_id']}"
            success = update_variant_metafields(
                variant_gid=variant_gid,
                s30=item["s30"],
                s120=item["s120"],
                rank=item["rank_30"],
                is_best=True
            )
            if success:
                success_count += 1

        print(f"✅ {success_count} best-sellers mis à jour")

        # 2️⃣ Créer un index combiné de TOUTES les variantes (top 120 + top 30)
        print("🔄 Création de l'index des variantes à vérifier...")
        
        # Index des ventes par variant_id
        all_variants = {}
        
        # Ajouter top 120
        for item in top_120:
            all_variants[item["variant_id"]] = {
                "variant_id": item["variant_id"],
                "product_title": item["product_title"],
                "variant_title": item["variant_title"],
                "s120": item["net_items_sold"],
                "s30": 0  # Sera mis à jour si dans top 30
            }
        
        # Ajouter/mettre à jour avec top 30
        for item in top_30:
            if item["variant_id"] in all_variants:
                all_variants[item["variant_id"]]["s30"] = item["net_items_sold"]
            else:
                # Variante dans top 30 mais pas top 120 (ventes très récentes)
                all_variants[item["variant_id"]] = {
                    "variant_id": item["variant_id"],
                    "product_title": item["product_title"],
                    "variant_title": item["variant_title"],
                    "s120": 0,
                    "s30": item["net_items_sold"]
                }
        
        print(f"📋 {len(all_variants)} variantes uniques à vérifier (top 120 + top 30)")

        # 3️⃣ Réinitialiser les variantes qui ne sont PLUS best-sellers
        reset_count = 0
        
        for variant_id, data in all_variants.items():
            # Si cette variante n'est PAS dans les best-sellers actuels
            if variant_id not in current_best_ids:
                variant_gid = f"gid://shopify/ProductVariant/{variant_id}"
                
                # Vérifier si elle a is_best_seller = true
                check_query = f"""
                {{
                  productVariant(id: "{variant_gid}") {{
                    metafield(namespace: "analytics", key: "is_best_seller") {{
                      value
                    }}
                  }}
                }}
                """
                
                check_result = shopify_graphql(check_query)
                
                # Si elle a is_best_seller = true, la réinitialiser
                if check_result and "data" in check_result:
                    variant_data = check_result["data"]["productVariant"]
                    
                    if variant_data and variant_data["metafield"] and variant_data["metafield"]["value"] == "true":
                        print(f"🔄 Réinitialisation de {variant_id} ({data['product_title']} - {data['variant_title']})")
                        
                        success = update_variant_metafields(
                            variant_gid=variant_gid,
                            s30=data["s30"],
                            s120=data["s120"],
                            rank=0,  # Plus de rank
                            is_best=False
                        )
                        
                        if success:
                            reset_count += 1

        print(f"✅ {reset_count} anciennes best-sellers réinitialisées")

        return {
            "status": "full sync complete",
            "current_best_sellers_updated": success_count,
            "old_best_sellers_reset": reset_count,
            "total_variants_checked": len(all_variants),
            "variants_in_top_120": len(top_120),
            "variants_in_top_30": len(top_30),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@best_sellers_bp.route("/sync/best_sellers_full")
def sync_best_sellers_full():
    try:
        result = run_full_best_seller_sync()
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




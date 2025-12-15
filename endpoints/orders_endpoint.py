from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import os
import requests

orders_bp = Blueprint("orders", __name__)


def shopify_graphql(query):
    """
    Exécute une requête GraphQL sur l'API Shopify Admin
    """
    shop_domain = os.getenv("MY_SHOPIFY_DOMAIN")
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


def fetch_all_orders_graphql(since_date):
    """
    Récupère toutes les commandes via GraphQL avec pagination
    """
    all_orders = []
    has_next_page = True
    cursor = None
    page = 1
    
    while has_next_page:
        print(f"📡 Récupération page {page} des commandes...")
        
        # Construire la requête avec ou sans cursor
        if cursor:
            after_clause = f'after: "{cursor}", '
        else:
            after_clause = ''
        
        query = f"""
        {{
          orders(first: 50, {after_clause}query: "created_at:>={since_date}") {{
            edges {{
              node {{
                id
                name
                createdAt
                test
                tags
                currentTotalPriceSet {{
                  shopMoney {{
                    amount
                  }}
                }}
                lineItems(first: 100) {{
                  edges {{
                    node {{
                      id
                      sku
                      quantity
                      variant {{
                        id
                      }}
                      product {{
                        id
                        vendor
                      }}
                      originalUnitPriceSet {{
                        shopMoney {{
                          amount
                        }}
                      }}
                      discountedUnitPriceSet {{
                        shopMoney {{
                          amount
                        }}
                      }}
                      discountAllocations {{
                        allocatedAmountSet {{
                          shopMoney {{
                            amount
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
                refunds {{
                  refundLineItems(first: 100) {{
                    edges {{
                      node {{
                        lineItem {{
                          id
                        }}
                        quantity
                        subtotalSet {{
                          shopMoney {{
                            amount
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """
        
        try:
            response = shopify_graphql(query)
            
            if 'errors' in response:
                print(f"❌ Erreurs GraphQL: {response['errors']}")
                break
            
            if response and 'data' in response and 'orders' in response['data']:
                orders_data = response['data']['orders']
                edges = orders_data.get('edges', [])
                
                print(f"✅ Page {page}: {len(edges)} commandes récupérées")
                
                all_orders.extend(edges)
                
                page_info = orders_data.get('pageInfo', {})
                has_next_page = page_info.get('hasNextPage', False)
                cursor = page_info.get('endCursor')
                
                page += 1
                
                if page > 100:
                    print(f"⚠️ Limite de 100 pages atteinte")
                    break
                
            else:
                print(f"⚠️ Structure de réponse inattendue")
                break
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération page {page}: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"\n✅ Total commandes récupérées: {len(all_orders)}\n")
    return all_orders


def generate_orders_data():
    """
    Récupère TOUTES les commandes des 365 derniers jours via GraphQL
    100% aligné avec Shopify Analytics
    """
    since = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    print(f"📅 Récupération des commandes depuis: {since}")
    
    try:
        orders_edges = fetch_all_orders_graphql(since)
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        return {"orders": []}

    result = []
    orders_excluded = 0
    testers_excluded = 0
    total_refunded_amount = 0.0
    total_refunded_qty = 0
    deleted_variants_count = 0

    for edge in orders_edges:
        order = edge['node']
        
        if order.get("test") == True:
            orders_excluded += 1
            continue
        
        tags = order.get("tags", [])
        if isinstance(tags, list):
            tags_lower = [t.lower() for t in tags]
            if any(tag in tags_lower for tag in ["test", "sample", "internal"]):
                orders_excluded += 1
                continue
        
        line_items = []
        
        for li_edge in order.get("lineItems", {}).get("edges", []):
            li = li_edge['node']
            
            sku = li.get("sku")
            quantity = li.get("quantity", 0) or 0
            
            # Extraire variant_id et product_id des GIDs
            variant_gid = li.get("variant", {}).get("id", "") if li.get("variant") else ""
            variant_id = variant_gid.split('/')[-1] if variant_gid else None
            
            product_gid = li.get("product", {}).get("id", "") if li.get("product") else ""
            product_id = product_gid.split('/')[-1] if product_gid else None
            
            # ✅ NOUVEAU : Récupérer le vendor (marque)
            vendor = li.get("product", {}).get("vendor", "Inconnue") if li.get("product") else "Inconnue"
            
            # Si variant_id est null, utiliser le line_item_id comme identifiant unique
            if not variant_id:
                # Variant supprimé - utiliser line_item_id comme fallback
                li_id = li.get("id", "")
                variant_id = f"deleted_{li_id.split('/')[-1]}" if li_id else None
                deleted_variants_count += 1
                
                if not variant_id:
                    continue
            
            # Prix unitaire original
            original_price = float(li.get("originalUnitPriceSet", {}).get("shopMoney", {}).get("amount", 0))
            discounted_price = float(li.get("discountedUnitPriceSet", {}).get("shopMoney", {}).get("amount", 0))
            
            # Exclure les testers (prix = 0)
            if original_price == 0:
                testers_excluded += 1
                continue
            
            discount = 0.0
            for discount_alloc in li.get("discountAllocations", []):
                discount += float(discount_alloc.get("allocatedAmountSet", {}).get("shopMoney", {}).get("amount", 0))
            
            refunded_qty = 0
            refunded_amount = 0.0
            
            li_id = li.get("id")
            for refund in order.get("refunds", []):
                for refund_li_edge in refund.get("refundLineItems", {}).get("edges", []):
                    refund_li = refund_li_edge['node']
                    
                    if refund_li.get("lineItem", {}).get("id") == li_id:
                        refunded_qty += refund_li.get("quantity", 0) or 0
                        refunded_amount += float(refund_li.get("subtotalSet", {}).get("shopMoney", {}).get("amount", 0))
            
            total_refunded_qty += refunded_qty
            total_refunded_amount += refunded_amount
            
            net_quantity = quantity - refunded_qty
            gross_sales = quantity * original_price
            net_sales = gross_sales - discount - refunded_amount
            
            line_items.append({
                "sku": sku,
                "product_id": product_id,
                "variant_id": variant_id,
                "vendor": vendor,  # ✅ NOUVEAU
                "quantity": net_quantity,
                "gross_sales": gross_sales,
                "discounts": discount,
                "refunds": refunded_amount,
                "net_sales": net_sales,
            })

        if line_items:
            result.append({
                "id": order.get("id", "").split('/')[-1],
                "name": order.get("name"),
                "created_at": order.get("createdAt"),
                "currency": "CAD",
                "total_price": float(order.get("currentTotalPriceSet", {}).get("shopMoney", {}).get("amount", 0)),
                "line_items": line_items,
            })

    print(f"📊 Total line_items traités : {sum(len(o['line_items']) for o in result)}")
    print(f"🎁 Testers exclus : {testers_excluded}")
    print(f"🚫 Commandes exclues : {orders_excluded}")
    print(f"🗑️ Variants supprimés capturés : {deleted_variants_count}")
    print(f"💸 Total refunds sur 365j : {total_refunded_amount:,.2f} $ ({total_refunded_qty} unités)\n")
    
    return {"orders": result}


@orders_bp.route("/data/orders")
def get_orders():
    """Endpoint HTTP pour les commandes"""
    try:
        data = generate_orders_data()
        return jsonify(data)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Erreur complète:\n{error_detail}")
        return jsonify({"error": f"Erreur : {e}", "detail": error_detail}), 500
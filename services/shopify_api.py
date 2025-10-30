import os, time, requests
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs

load_dotenv()
SHOP_NAME = os.getenv("SHOP_NAME")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
API_VER = "2024-10"
BASE_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{API_VER}"
HEADERS = {"X-Shopify-Access-Token": ACCESS_TOKEN, "Content-Type": "application/json"}

def _safe_get(url, params=None):
    for _ in range(6):
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", "1")) or 1)
            continue
        if not r.ok:
            print("❌ Erreur Shopify:", r.text)
            r.raise_for_status()
        time.sleep(0.55)  # ~2 req/s
        return r
    raise RuntimeError("Trop de 429")

def shopify_get(endpoint, params=None):
    r = _safe_get(f"{BASE_URL}/{endpoint}", params=params)
    return r.json()

def _next_page_info(link_header: str | None):
    if not link_header: return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            url = part.split(";")[0].strip().strip("<>")
            return parse_qs(urlparse(url).query).get("page_info", [None])[0]
    return None

def shopify_get_all(endpoint, initial_params=None, root_key=None):
    params = dict(initial_params or {})
    params.setdefault("limit", 250)
    url = f"{BASE_URL}/{endpoint}"

    items = []
    # 1re page avec filtres
    r = _safe_get(url, params=params)
    data = r.json()
    if root_key:
        items.extend(data.get(root_key, []))
    else:
        if isinstance(data, list): items.extend(data)
        else:
            for k, v in data.items():
                if isinstance(v, list): items.extend(v); break
    page_info = _next_page_info(r.headers.get("Link"))

    # pages suivantes: uniquement page_info + limit
    base_params = {"limit": params["limit"]}
    while page_info:
        p = dict(base_params, page_info=page_info)
        r = _safe_get(url, params=p)
        d = r.json()
        if root_key:
            items.extend(d.get(root_key, []))
        else:
            if isinstance(d, list): items.extend(d)
            else:
                for k, v in d.items():
                    if isinstance(v, list): items.extend(v); break
        page_info = _next_page_info(r.headers.get("Link"))
    return items

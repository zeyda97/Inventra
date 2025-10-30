from flask import Flask, render_template, redirect, url_for
from endpoints.products_endpoint import products_bp
from endpoints.orders_endpoint import orders_bp
from endpoints.locations_endpoint import locations_bp
from endpoints.inventory_endpoint import inventory_bp
from endpoints.report_endpoint import report_bp
from endpoints.dashboard_endpoint import dashboard_bp

app = Flask(__name__)

# Enregistrement des Blueprints
app.register_blueprint(products_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(locations_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(report_bp)
app.register_blueprint(dashboard_bp)

@app.route("/")
def home():
    """Redirige automatiquement vers le tableau de bord"""
    return redirect(url_for('dashboard_static'))

@app.route("/home")
def home_page():
    """Page d'accueil avec tous les liens"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Inventra API - Shopify Reporting</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h2 { color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px; }
            ul { list-style: none; padding: 0; }
            li { margin: 15px 0; }
            a { display: block; padding: 12px 20px; background: #007cba; color: white; text-decoration: none; border-radius: 5px; transition: background 0.3s; }
            a:hover { background: #005a87; }
            .exit-btn { background: #dc3545; margin-top: 30px; }
            .exit-btn:hover { background: #c82333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Inventra API - Shopify Reporting</h2>
            <ul>
                <li><a href="/data/products">/data/products</a></li>
                <li><a href="/data/orders">/data/orders</a></li>
                <li><a href="/data/locations">/data/locations</a></li>
                <li><a href="/data/inventory">/data/inventory</a></li>
                <li><a href="/report">/report (API JSON)</a></li>
                <li><a href="/dashboard_static">📊 Tableau de Bord Principal</a></li>
                <li><a href="/forecast/Frapin">/forecast/&lt;marque&gt;</a></li>
            </ul>
            <a href="/dashboard_static" class="exit-btn">🚪 Quitter vers le Tableau de Bord</a>
        </div>
    </body>
    </html>
    """

# ✅ Route Flask du tableau de bord statique (SÉCURISÉE)
@app.route("/dashboard_static")
def dashboard_static():
    """Tableau de bord statique (sans JS)"""
    try:
        # ✅ Appel DIRECT à la logique métier sans HTTP
        from endpoints.report_endpoint import generate_report_data
        data = generate_report_data()
    except Exception as e:
        print("❌ Erreur génération rapport :", e)
        data = []

    return render_template("dashboard_static.html", data=data)

# ✅ Route de sortie/retour
@app.route("/exit")
def exit_to_home():
    """Redirige vers la page d'accueil"""
    return redirect(url_for('home_page'))

# ✅ Lancement du serveur
if __name__ == "__main__":
    app.run(debug=True, port=5000)
# from flask import Flask, render_template
# import requests
# from endpoints.products_endpoint import products_bp
# from endpoints.orders_endpoint import orders_bp
# from endpoints.locations_endpoint import locations_bp
# from endpoints.inventory_endpoint import inventory_bp
# from endpoints.report_endpoint import report_bp
# # from endpoints.forecast_endpoint import forecast_bp
# from endpoints.dashboard_endpoint import dashboard_bp  
# # ✅ Nouveau import

# app = Flask(__name__)

# # Enregistrement des Blueprints
# app.register_blueprint(products_bp)
# app.register_blueprint(orders_bp)
# app.register_blueprint(locations_bp)
# app.register_blueprint(inventory_bp)
# app.register_blueprint(report_bp)
# # app.register_blueprint(forecast_bp)
# app.register_blueprint(dashboard_bp)  # ✅ Enregistrement ici


# @app.route("/")
# def home():
#     return """
#     <h2>Inventra API - Shopify Reporting</h2>
#     <ul>
#       <li><a href="/data/products">/data/products</a></li>
#       <li><a href="/data/orders">/data/orders</a></li>
#       <li><a href="/data/locations">/data/locations</a></li>
#       <li><a href="/data/inventory">/data/inventory</a></li>
#       <li><a href="/report">/report</a></li>
#       <li><a href="/dashboard_static">/dashboard_static</a></li>
#       <li><a href="/forecast/Frapin">/forecast/&lt;marque&gt;</a></li>
#     </ul>
#     """


# # ✅ Route Flask du tableau de bord statique
# @app.route("/dashboard_static")
# def dashboard_static():
#     """Tableau de bord statique (sans JS)"""
#     try:
#         res = requests.get("http://127.0.0.1:5000/report")
#         data = res.json()
#     except Exception as e:
#         print("❌ Erreur rapport :", e)
#         data = []

#     return render_template("dashboard_static.html", data=data)


# # ✅ Lancement du serveur
# if __name__ == "__main__":
#     app.run(debug=True, port=5000)


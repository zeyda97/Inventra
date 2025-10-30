from flask import Flask, render_template
import requests
from endpoints.products_endpoint import products_bp
from endpoints.orders_endpoint import orders_bp
from endpoints.locations_endpoint import locations_bp
from endpoints.inventory_endpoint import inventory_bp
from endpoints.report_endpoint import report_bp
# from endpoints.forecast_endpoint import forecast_bp
from endpoints.dashboard_endpoint import dashboard_bp  
# ✅ Nouveau import

app = Flask(__name__)

# Enregistrement des Blueprints
app.register_blueprint(products_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(locations_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(report_bp)
# app.register_blueprint(forecast_bp)
app.register_blueprint(dashboard_bp)  # ✅ Enregistrement ici


@app.route("/")
def home():
    return """
    <h2>Inventra API - Shopify Reporting</h2>
    <ul>
      <li><a href="/data/products">/data/products</a></li>
      <li><a href="/data/orders">/data/orders</a></li>
      <li><a href="/data/locations">/data/locations</a></li>
      <li><a href="/data/inventory">/data/inventory</a></li>
      <li><a href="/report">/report</a></li>
      <li><a href="/dashboard_static">/dashboard_static</a></li>
      <li><a href="/forecast/Frapin">/forecast/&lt;marque&gt;</a></li>
    </ul>
    """


# ✅ Route Flask du tableau de bord statique
@app.route("/dashboard_static")
def dashboard_static():
    """Tableau de bord statique (sans JS)"""
    try:
        res = requests.get("http://127.0.0.1:5000/report")
        data = res.json()
    except Exception as e:
        print("❌ Erreur rapport :", e)
        data = []

    return render_template("dashboard_static.html", data=data)


# ✅ Lancement du serveur
if __name__ == "__main__":
    app.run(debug=True, port=5000)


from flask import Flask, render_template, redirect, url_for
from endpoints.products_endpoint import products_bp
from endpoints.orders_endpoint import orders_bp
from endpoints.locations_endpoint import locations_bp
from endpoints.inventory_endpoint import inventory_bp
from endpoints.report_endpoint import report_bp
from endpoints.dashboard_endpoint import dashboard_bp
from endpoints.best_sellers_endpoint import best_sellers_bp

app = Flask(__name__)

# Enregistrement des Blueprints
app.register_blueprint(products_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(locations_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(report_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(best_sellers_bp)


@app.route("/")
def home():
    """Redirige automatiquement vers le tableau de bord"""
    return redirect(url_for('dashboard_static'))

@app.route("/home")
def home_page():
    return render_template("home.html")


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

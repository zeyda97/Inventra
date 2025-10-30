# ============================================================
# Étape 1 : Utiliser une image Python stable et légère
# ============================================================
FROM python:3.11-slim

# ============================================================
# Étape 2 : Définir le répertoire de travail
# ============================================================
WORKDIR /app

# ============================================================
# Étape 3 : Copier les fichiers nécessaires dans le conteneur
# ============================================================
COPY . .

# ============================================================
# Étape 4 : Mettre à jour pip et installer les dépendances
# ------------------------------------------------------------
# --no-cache-dir évite de stocker les fichiers d’installation
# ============================================================
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================
# Étape 5 : Exposer le port sur lequel l’app tourne
# ============================================================
EXPOSE 5000

# ============================================================
# Étape 6 : Commande pour lancer Flask via Gunicorn
# ------------------------------------------------------------
# "app:app" fait référence au fichier app.py et à l'objet Flask nommé app
# Si ton fichier principal s’appelle autrement (ex: main.py),
# remplace app:app par main:app
# ============================================================
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

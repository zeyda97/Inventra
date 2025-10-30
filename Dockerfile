# ==========================
# 🐍 Étape 1 : Choisir l’image Python
# ==========================
FROM python:3.11-slim

# ==========================
# 📁 Étape 2 : Créer un répertoire de travail
# ==========================
WORKDIR /app

# ==========================
# 📦 Étape 3 : Copier les fichiers nécessaires
# ==========================
COPY requirements.txt .

# ==========================
# 🧰 Étape 4 : Installer les dépendances
# ==========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    libopenblas-dev \
    libfreetype6-dev \
    libpng-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# ==========================
# 🗂️ Étape 5 : Copier le reste du code
# ==========================
COPY . .

# ==========================
# 🌍 Étape 6 : Variables d'environnement
# ==========================
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# ==========================
# 🚀 Étape 7 : Commande de lancement
# ==========================
# ⚠️ Important : utiliser /bin/sh -c pour que $PORT soit évalué par le shell
#CMD ["/bin/sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT}"]
# ==========================
# 🚀 Étape 7 : Commande de lancement (APRÈS - CORRIGÉE)
# ==========================
CMD ["/bin/sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT} --timeout 300 --workers 1 --preload"]

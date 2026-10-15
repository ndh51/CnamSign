#!/bin/sh
set -e

cd /app

if [ -d "/app/.git" ]; then
    echo "[DOCKER] Vérification des mises à jour distantes (git pull)..."
    git config --global --add safe.directory /app || true
    git config --global --add safe.directory '*' || true
    if git pull origin main; then
        echo "[DOCKER] Code distant synchronisé avec succès."
    else
        echo "[DOCKER] Avertissement : impossible de synchroniser avec GitHub (hors-ligne ou conflit). Utilisation du code local."
    fi
else
    echo "[DOCKER] Aucun dossier .git détecté, lancement avec le code embarqué."
fi

exec "$@"

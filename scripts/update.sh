#!/bin/bash
# Mise à jour — git pull + rebuild + restart
set -e

REPO=/home/debian/meteo

echo "=== Pull ==="
cd "$REPO"
git pull origin main

echo "=== Backend : dépendances ==="
cd "$REPO/backend"
venv/bin/pip install -q -r requirements.txt

echo "=== Frontend : tests + build ==="
cd "$REPO/frontend"
npm ci --silent
# set -e arrête le déploiement si la suite échoue : un runner que rien
# n'exécute automatiquement ne protège que ceux qui pensent à le lancer
npm test
npm run build

echo "=== Restart ==="
sudo systemctl restart maison-temp

sleep 2
systemctl is-active maison-temp && echo "✓ Service actif" || echo "✗ Service inactif"
curl -sf http://127.0.0.1:8042/api/sondes > /dev/null && echo "✓ API OK" || echo "✗ API KO"

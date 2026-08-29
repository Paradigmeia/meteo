#!/bin/bash
# Mise à jour — git pull + rebuild + restart
set -e

REPO=/home/debian/meteo

# Le pull peut mettre à jour ce script lui-même. bash lit un script par
# position d'octet au fil de l'exécution : continuer après un pull qui a décalé
# les lignes fait exécuter un mélange des deux versions — au mieux une étape
# sautée (c'est ce qui est arrivé au déploiement du 2026-08-29, où le npm test
# tout juste ajouté n'a pas tourné), au pire une ligne tronquée. On se relance
# donc explicitement dans la version fraîchement tirée, une seule fois.
if [ "$1" != "--relance" ]; then
  echo "=== Pull ==="
  cd "$REPO"
  git pull origin main
  echo "=== Relance dans la version à jour ==="
  exec bash "$REPO/scripts/update.sh" --relance
fi

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

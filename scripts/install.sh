#!/bin/bash
# Premier déploiement — à lancer une seule fois sur le serveur
set -e

REPO=/home/debian/meteo

echo "=== 1. Backend : venv + dépendances ==="
cd "$REPO/backend"
python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "=== 2. Backend : .env ==="
if [ ! -f .env ]; then
    cp "$REPO/.env.example" .env
    TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change-me-with-a-strong-random-token/$TOKEN/" .env
    echo "⚠️  .env créé avec un token aléatoire — vérifier DATABASE_PATH si besoin"
fi
mkdir -p data

echo "=== 3. Frontend : build ==="
cd "$REPO/frontend"
npm ci --silent
npm run build

echo "=== 4. Nginx ==="
sudo cp "$REPO/nginx/maison-temp.conf" /etc/nginx/sites-available/maison-temp
sudo ln -sf /etc/nginx/sites-available/maison-temp /etc/nginx/sites-enabled/maison-temp
sudo nginx -t
sudo systemctl reload nginx

echo "=== 5. Certbot ==="
sudo certbot certonly --webroot -w /var/www/html -d meteo.paradigme.me --non-interactive --agree-tos -m admin@paradigme.me
sudo systemctl reload nginx

echo "=== 6. systemd ==="
sudo cp "$REPO/maison-temp.service" /etc/systemd/system/maison-temp.service
sudo systemctl daemon-reload
sudo systemctl enable maison-temp
sudo systemctl start maison-temp

echo ""
echo "=== Smoke tests ==="
sleep 2
systemctl is-active maison-temp && echo "✓ Service actif" || echo "✗ Service inactif"
curl -sf http://127.0.0.1:8042/api/sondes > /dev/null && echo "✓ API /api/sondes répond" || echo "✗ API muette"
curl -sf https://meteo.paradigme.me > /dev/null && echo "✓ HTTPS accessible" || echo "✗ HTTPS KO"

echo ""
echo "=== Terminé ==="
echo "Logs : journalctl -u maison-temp -f"
echo "Token API : grep API_KEY $REPO/backend/.env"

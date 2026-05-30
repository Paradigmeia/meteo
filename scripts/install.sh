#!/bin/bash
# Premier déploiement — à lancer une seule fois sur le serveur
set -e

REPO=/home/debian/meteo

echo "=== Vérification des prérequis ==="
for cmd in nginx certbot python3 node npm; do
    command -v $cmd &>/dev/null || { echo "✗ $cmd manquant"; exit 1; }
done
echo "✓ Prérequis OK"

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
    chmod 600 .env
    echo "⚠️  .env créé — token API :"
    echo "   $TOKEN"
fi
mkdir -p data

echo "=== 3. Frontend : build ==="
cd "$REPO/frontend"
npm ci --silent
npm run build

# Bootstrap : conf HTTP-only d'abord pour que Certbot puisse valider
echo "=== 4a. Nginx : conf HTTP-only (bootstrap Certbot) ==="
cat > /tmp/maison-temp-bootstrap.conf <<'NGINX'
server {
    listen 80;
    server_name meteo.paradigme.me;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$host$request_uri; }
}
NGINX
sudo cp /tmp/maison-temp-bootstrap.conf /etc/nginx/sites-available/maison-temp
sudo ln -sf /etc/nginx/sites-available/maison-temp /etc/nginx/sites-enabled/maison-temp
sudo nginx -t
sudo systemctl reload nginx

echo "=== 4b. Certbot ==="
sudo certbot certonly --webroot -w /var/www/html -d meteo.paradigme.me \
    --non-interactive --agree-tos -m admin@paradigme.me

echo "=== 4c. Nginx : conf complète HTTPS ==="
sudo cp "$REPO/nginx/maison-temp.conf" /etc/nginx/sites-available/maison-temp
sudo nginx -t
sudo systemctl reload nginx

echo "=== 5. systemd ==="
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
echo "Test webhook :"
echo "  curl -X POST https://meteo.paradigme.me/api/releve/salon \\"
echo "    -H \"X-API-Key: \$(grep API_KEY $REPO/backend/.env | cut -d= -f2)\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"temp\":21.5,\"hum\":55}'"

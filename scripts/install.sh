#!/bin/bash
# Premier déploiement — à lancer une seule fois sur le serveur
set -e

REPO=/home/debian/meteo

echo "=== Vérification des prérequis ==="
for cmd in nginx certbot python3 node npm; do
    command -v $cmd &>/dev/null || sudo bash -c "command -v $cmd" &>/dev/null || \
        { echo "✗ $cmd manquant"; exit 1; }
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

echo "=== 6. sudo sans mot de passe pour le seul restart de maison-temp ==="
# scripts/update.sh se termine par un `sudo systemctl restart maison-temp` suivi
# de deux contrôles de santé. Hors terminal interactif (script, tâche planifiée),
# sudo ne peut pas demander de mot de passe : le restart échoue et, sous `set -e`,
# le déploiement se termine sans jamais afficher son verdict.
#
# Le chemin inscrit dans la règle doit être celui que sudo résoudra à l'appel, et
# sudo n'utilise pas le PATH de l'utilisateur mais son propre `secure_path`. Sur
# cette machine les deux diffèrent : le PATH de `debian` commence par
# ~/.local/bin et ~/bin, deux répertoires qu'il peut écrire, et ne contient pas
# /usr/sbin. Un `command -v systemctl` y trouverait un homonyme et poserait soit
# une règle qui ne s'applique jamais, soit — bien pire — un NOPASSWD sur un
# binaire que `debian` peut réécrire, c'est-à-dire root sans mot de passe. On
# cherche donc dans les répertoires système, dans l'ordre de `secure_path`.
SYSTEMCTL=""
for d in /usr/local/sbin /usr/local/bin /usr/sbin /usr/bin /sbin /bin; do
    if [ -x "$d/systemctl" ]; then SYSTEMCTL="$d/systemctl"; break; fi
done
[ -n "$SYSTEMCTL" ] || { echo "✗ systemctl introuvable dans les répertoires système"; exit 1; }
# Une règle NOPASSWD ne vaut que ce que vaut le binaire qu'elle vise.
[ -n "$(find "$SYSTEMCTL" -maxdepth 0 -user root ! -perm /022)" ] || \
    { echo "✗ $SYSTEMCTL n'appartient pas à root ou est modifiable par d'autres"; exit 1; }

# mktemp plutôt qu'un nom fixe dans /tmp : le fichier est écrit par `debian`
# puis installé par root, et un nom prévisible dans un répertoire ouvert à tous
# est un point d'entrée par lien symbolique.
SUDOERS_TMP=$(mktemp)
trap 'rm -f "$SUDOERS_TMP"' EXIT
cat > "$SUDOERS_TMP" <<SUDOERS
debian ALL=(root) NOPASSWD: $SYSTEMCTL restart maison-temp
SUDOERS
# Jamais de pose sans contrôle préalable : une erreur de syntaxe dans
# /etc/sudoers.d verrouille sudo sur la machine — y compris pour la réparer.
sudo visudo -cf "$SUDOERS_TMP"
# Pose atomique. `install` écrit dans le fichier de destination : interrompu, il
# y laisserait une ligne tronquée, soit exactement la panne que le contrôle
# ci-dessus cherche à éviter. On installe sous un nom que sudo ignore — il saute
# les fichiers dont le nom contient un point — puis on renomme, ce qui est
# atomique à l'intérieur d'un même système de fichiers.
sudo install -o root -g root -m 0440 "$SUDOERS_TMP" /etc/sudoers.d/.maison-temp.nouveau
sudo mv /etc/sudoers.d/.maison-temp.nouveau /etc/sudoers.d/maison-temp

echo ""
echo "=== Smoke tests ==="
# `sudo -l <commande>` répond « autorisée ? », pas « autorisée sans mot de
# passe ? » : `debian` ayant déjà (ALL : ALL) ALL, il répond oui à tout, y
# compris à `restart nginx`, et ne prouverait donc rien. Le seul contrôle qui
# porte est d'exécuter la commande avec -n — cache d'authentification vidé au
# préalable, sans quoi les sudo des étapes précédentes la feraient passer quelle
# que soit la règle.
sudo -k
sudo -n "$SYSTEMCTL" restart maison-temp 2>/dev/null \
    && echo "✓ restart sans mot de passe autorisé" \
    || echo "✗ règle sudoers inopérante — update.sh s'arrêtera avant ses contrôles"
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

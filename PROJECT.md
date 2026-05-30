# PROJECT.md — maison-temp

## Références

- [SPEC.md](SPEC.md) : cahier des charges fonctionnel
- [PLAN.md](PLAN.md) : architecture technique, arborescence, décisions

## État du projet

| LOT | Contenu | Statut | PR | Branch |
|---|---|---|---|---|
| LOT 1 | Backend FastAPI — réception webhooks + SQLite | ✅ Livré | #5 | lot1-backend |
| LOT 2 | Frontend React — dashboard temps réel | ✅ Livré | #6 | lot2-frontend |
| LOT 3 | Frontend React — historique + graphiques | 🗄️ Abandonné — absorbé par LOT 2 (2026-05-30) | — | — |
| LOT 4 | Déploiement OVH — Nginx + systemd + HTTPS | ✅ Livré | #7 | lot4-deploy |

Légende : 🔲 À faire · 🔄 En cours · ✅ Livré · ⚠️ Dette technique · 🗄️ Abandonné

### Features hors LOT

| Feature | Statut | PR | Issue |
|---|---|---|---|
| Alertes seuil (ex: gel extérieur) | 🔲 À faire (v2) | — | — |
| Auth dashboard (si accès public élargi) | 🔲 À faire (v2) | — | — |

---

## Changelog

### 2026-05-30 — LOT 4 livré + déployé

- Déploiement OVH opérationnel (PR #7, mergée)
- `https://meteo.paradigme.me` accessible, certificat Let's Encrypt valide (expire 2026-08-28)
- Nginx : reverse proxy `/api/` → FastAPI :8042, build React statique, HSTS, redirection HTTP→HTTPS
- systemd `maison-temp.service` actif, démarrage auto au boot, hardening (`NoNewPrivileges`, `ProtectSystem`, `PrivateTmp`)
- CORS restreint à `https://meteo.paradigme.me`
- `scripts/install.sh` et `scripts/update.sh` opérationnels
- Token API généré et stocké dans `backend/.env` (chmod 600)
- Smoke tests post-déploiement : webhook, API sondes, HTTPS → tous verts

### 2026-05-30 — LOT 2 livré

- Frontend React opérationnel (PR #6, mergée)
- `MeteoCard` : conditions actuelles Open-Meteo, bandeau horaire 24h scrollable, prévision J+1
- `SondeCard` : température, humidité (null-safe), timestamp, badge Hors ligne si inactivité > 3h
- `Detail` : graphique SVG dual-axis température + humidité, sélecteur 24h / 7j / 30d
- Polling 30s sur les 3 hooks (`useSondes`, `useMeteo`, `useReleves`), StrictMode-safe
- Layout mobile-first 390px, charte crème/ambre/teal fidèle au mockup validé
- **LOT 3 clôturé** : la vue Détail avec graphique SVG dual-axis et sélecteur 24h/7j/30d couvre l'intégralité du scope LOT 3 — absorbé par ce LOT.
- Prochaine étape : LOT 3 (périmètre à revalider) puis LOT 4 — déploiement OVH

### 2026-05-29 — LOT 1 livré

- Backend FastAPI opérationnel (PR #5, mergée)
- 4 endpoints : `POST /api/releve/{slug}`, `GET /api/sondes`, `GET /api/releves/{slug}`, `GET /api/meteo`
- SQLite + 4 sondes pré-remplies, auth X-API-Key, proxy Open-Meteo avec cache 30min
- Prochaine étape : LOT 2 — dashboard React

### 2026-05-23 — Session UI template + prévisionnel horaire (spec amendée)

- Maquette interactive dashboard validée (`maison-temp-mockup.html`)
- Charte graphique actée : tons chauds crème/sable, ambre température, teal humidité (cf. SPEC.md §5)
- Navigation actée : tap card → vue détail avec historique, bouton retour
- Structure dashboard actée : météo en tête, sections Intérieur / Extérieur séparées
- État hors ligne : badge "Hors ligne" + card pleine largeur, timestamp en rouge
- Prévisionnel horaire ajouté au bloc météo : bandeau scrollable 24h (heure, icône, temp, précip)
- SPEC.md v1.0 → v1.1 : §4.5 restructuré (météo), §5 ajouté (charte graphique et UI template)
- Prochaine étape : LOT 2 — dashboard React

### 2026-05-23 — Initialisation du projet

- Définition du besoin : suivi températures + humidité, 4 sondes (3 intérieur + 1 extérieur)
- Hardware acté : Shelly H&T Gen3 (WiFi, webhook HTTP natif, ~20€/unité)
- Stratégie démarrage : 1 sonde achetée pour validation, 3 autres à suivre
- Stack actée : FastAPI + SQLite + React + Chart.js + Nginx + OVH
- Sous-domaine acté : `meteo.domaine.fr` (domaine principal à confirmer)
- Météo Ascain : Open-Meteo double modèle AROME + ECMWF, cache 30min
- Rédaction SPEC.md v1.0, PLAN.md v1.0, PROJECT.md v1.0

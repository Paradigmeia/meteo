# PROJECT.md — maison-temp

## Références

- [SPEC.md](SPEC.md) : cahier des charges fonctionnel
- [PLAN.md](PLAN.md) : architecture technique, arborescence, décisions

## État du projet

| LOT | Contenu | Statut | PR | Branch |
|---|---|---|---|---|
| LOT 1 | Backend FastAPI — réception webhooks + SQLite | ✅ Livré | #5 | lot1-backend |
| LOT 2 | Frontend React — dashboard temps réel | 🔲 À faire | — | — |
| LOT 3 | Frontend React — historique + graphiques | 🔲 À faire | — | — |
| LOT 4 | Déploiement OVH — Nginx + systemd + HTTPS | 🔲 À faire | — | — |

Légende : 🔲 À faire · 🔄 En cours · ✅ Livré · ⚠️ Dette technique · 🗄️ Abandonné

### Features hors LOT

| Feature | Statut | PR | Issue |
|---|---|---|---|
| Alertes seuil (ex: gel extérieur) | 🔲 À faire (v2) | — | — |
| Auth dashboard (si accès public élargi) | 🔲 À faire (v2) | — | — |

---

## Changelog

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

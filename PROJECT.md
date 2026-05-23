# PROJECT.md — maison-temp

## Références

- [SPEC.md](SPEC.md) : cahier des charges fonctionnel
- [PLAN.md](PLAN.md) : architecture technique, arborescence, décisions

## État du projet

| LOT | Contenu | Statut | PR | Branch |
|---|---|---|---|---|
| LOT 1 | Backend FastAPI — réception webhooks + SQLite | 🔲 À faire | — | — |
| LOT 2 | Frontend React — dashboard temps réel | 🔲 À faire | — | — |
| LOT 3 | Frontend React — historique + graphiques | 🔲 À faire | — | — |
| LOT 4 | Déploiement OVH — Nginx + systemd + HTTPS | 🔲 À faire | — | — |

> **⏸ Session en pause — 2026-05-23**
> Spec et architecture complètement validées. Prochaine session : décisions sur la **template UI** (mise en page, charte graphique, composants) avant toute implémentation.

Légende : 🔲 À faire · 🔄 En cours · ✅ Livré · ⚠️ Dette technique · 🗄️ Abandonné

### Features hors LOT

| Feature | Statut | PR | Issue |
|---|---|---|---|
| Alertes seuil (ex: gel extérieur) | 🔲 À faire (v2) | — | — |
| Auth dashboard (si accès public élargi) | 🔲 À faire (v2) | — | — |

## Changelog

### 2026-05-23 — Initialisation du projet

- Définition du besoin : suivi températures + humidité, 4 sondes (3 intérieur + 1 extérieur)
- Hardware acté : Shelly H&T Gen3 (WiFi, webhook HTTP natif, ~20€/unité)
- Stratégie démarrage : 1 sonde achetée pour validation, 3 autres à suivre
- Stack actée : FastAPI + SQLite + React + Chart.js + Nginx + OVH
- Sous-domaine acté : `meteo.domaine.fr` (domaine principal à confirmer)
- Ajout feature météo locale Ascain : Open-Meteo double modèle (AROME + ECMWF), affichage comparatif, cache 30min
- **Fin de session** : spec et archi validées, prochaine session sur la template UI
- Rédaction SPEC.md v1.0, PLAN.md v1.0, PROJECT.md v1.0

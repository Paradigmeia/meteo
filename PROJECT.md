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

### 2026-06-20 — Activation de la sonde extérieure (boîtier physique installé)

- Boîtier Shelly H&T Gen3 extérieur installé physiquement (boîtier abrité, cf. PLAN.md décision 1)
- Base de production (`data/maison.db`) : `UPDATE sondes SET actif = 1 WHERE slug = 'exterieur'` — la ligne existait depuis le LOT 1 (PLAN.md décision 4 : ajouter une sonde = donnée en base, pas de code), seul le flag d'activation manquait
- Aucun changement de code : le dashboard affiche déjà la sonde (section "Extérieur" déjà câblée dans `Dashboard.jsx` sur le préfixe de slug `ext*`), en attente du premier relevé webhook
- Config Shelly à saisir côté boîtier (2 actions "URL action" — cf. SPEC.md §4.1) :
  - Changement de température → `https://meteo.paradigme.me/api/releve/exterieur?temp=${ev.tC}&key=<API_KEY>`
  - Changement d'humidité → `https://meteo.paradigme.me/api/releve/exterieur?hum=${ev.rh}&key=<API_KEY>`
  - `<API_KEY>` : valeur stockée dans `backend/.env`

### 2026-06-20 — Issue #14 : panneau de survol fixe remplaçant le tooltip flottant

- **`HistoriqueChart.jsx`** : suppression du tooltip flottant SVG (bulle + texte) — conservation
  d'une simple ligne verticale de repérage (`#1A1714`, opacité 0.15). La recherche du point
  survolé se fait désormais indépendamment sur les relevés température et humidité (au lieu
  d'un seul relevé combiné), ce qui corrige le bug où une seule des deux valeurs s'affichait
  selon la courbe la plus proche du point de contact
- **`HistoriqueChart.jsx`** : nouvelle prop `onHover(releve|null)` — notifie le parent du point
  survolé/touché ; `null` à la sortie du curseur en desktop, valeur conservée après `touchend`
  sur mobile (pas de handler dédié)
- **`SurvolPanel.jsx`** (nouveau composant) : panneau fixe inséré entre le sélecteur de période
  et la carte graphique — heure (format adapté à la période), température (ambre) et humidité
  (teal) ; état "repos" grisé (dernier relevé de la période) quand rien n'est survolé
- **`chartUtils.js`** : nouvelle fonction `formatHoverLabel(date, period)` — `HH:mm` pour
  12h/24h, `lun. 12 juin` pour 7j, `12 juin` pour 30j
- **`Detail.jsx`** : état `hovered` câblé sur `HistoriqueChart`, remis à `null` au changement de
  période (le graphique est remonté via `key={period}`)
- **`App.css`** : styles `.hover-panel` — fond `#EDE6DB` (comme les metric cards), hauteur fixe
  pour éviter tout layout shift
- **`SPEC.md`** §4.3 amendée : description du panneau de survol fixe + mention de la période
  `12h` (omise depuis #12)

### 2026-06-18 — Issue #12 : ajout de la période 12h dans la vue détail sonde

- **`GET /api/releves/{slug}?period=12h`** : nouvelle valeur acceptée — fenêtre `NOW() - 12 heures`, données brutes (même logique que `24h`, pas d'agrégation par bucket)
- **`frontend/src/components/Detail.jsx`** : bouton `12h` ajouté en première position dans `PERIODS`; `24h` reste le défaut à l'ouverture
- **`frontend/src/utils/chartUtils.js`** : cas `'12h'` ajouté dans `getXTicks` — ticks toutes les 2h

### 2026-06-15 — Fix webhook Shelly : tolérance aux valeurs `null` littérales

- **`GET /api/releve/{slug}`** : `temp` et `hum` acceptés en `str` puis convertis via `_parse_shelly_value` — la chaîne littérale `"null"` (envoyée par le firmware HTG3 quand `${ev.tC}`/`${ev.h}` est absent du rapport déclencheur) est traitée comme valeur absente au lieu de provoquer un 422
- Cause : un rapport déclenché par un changement de température ne contient pas `ev.h`, donc l'action "Changement d'humidité" envoyait `hum=null`, rejeté par l'API → perte des relevés d'humidité depuis le 14/06
- **`backend/test_main.py`** (nouveau) : tests sur `_parse_shelly_value` et sur l'endpoint (`null` ignoré, clé invalide, valeur invalide → 422)
- **`backend/requirements-dev.txt`** (nouveau) : ajout `pytest==9.1.0` pour exécuter la suite de tests

### 2026-06-04 — Issue #9 : graphique historique enrichi (axes, tooltip, min/max, densité adaptative)

- **`HistoriqueChart.jsx`** (nouveau composant) : axes Y gradués temperature (ambre, 4 ticks) et humidité (teal, 3 ticks), grille horizontale sur les ticks température, grille verticale pointillée sur les ticks X
- **Axe X** : labels temporels contextuels — 24h toutes les 3h (`14h`), 7d par jour (`Lun`…), 30d tous les 5 jours (`12/5`…)
- **Tooltip interactif** : curseur + bulle `#1A1714` au hover/touch, heure + temp + humidité, ancrage inversé si proche du bord droit
- **Indicateurs min/max** : labels `▲`/`▼` flottants au-dessus/en-dessous des extrema température et humidité, clampés dans le viewBox
- **Densité adaptative backend** : `GET /api/releves/{slug}?period=7d` → agrégation 3h (≤56 pts), `period=30d` → agrégation 12h (≤60 pts), `period=24h` → données brutes
- **`chartUtils.js`** (nouveau) : `niceTicks`, `linearScale`, `smooth`, `getXTicks` encapsulés séparément du rendu
- `Detail.jsx` mis à jour : import `HistoriqueChart`, passage du prop `period`, height viewBox 200px

### 2026-06-01 — Hotfixes intégration Shelly H&T Gen3 (commits directs sur main, rattrapage §4.1 workflow)

- **Endpoint GET webhook** : ajout de `GET /api/releve/{slug}?temp=X&hum=Y&key=TOKEN` — le firmware Shelly HTG3/1.7.5 ne supporte que les URL actions GET (SPEC §4.1 mise à jour)
- **Events séparés** : le Shelly envoie temp et hum sur deux events distincts → `temp` et `hum` tous les deux optionnels, deux actions Shelly à configurer
- **Migration DB** : `temperature` rendue nullable (était `NOT NULL`) pour accepter les inserts hum-only
- **Fix `/api/sondes`** : le `dernier_releve` agrège maintenant le dernier temp ET la dernière hum via deux LEFT JOIN séparés
- **Fix `Detail.jsx`** : `lastTemp` et `lastHum` cherchés séparément dans les relevés (évite l'affichage `—` quand la dernière ligne est hum-only)
- **Fix Open-Meteo** : suppression du paramètre `&models=` qui préfixait les noms de champs et cassait l'affichage météo (PLAN.md décision 8)
- SPEC.md et PLAN.md mis à jour (décisions 6, 7, 8)

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

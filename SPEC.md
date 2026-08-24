# SPEC.md — maison-temp

**Version** : 1.5
**Date** : 2026-08-24
**Objectif principal** : Suivre en temps réel et en historique les températures et taux d'humidité de la maison (intérieur + extérieur) via un dashboard web responsive accessible en ligne.

---

## 1. Contexte & Philosophie

### 1.1 Utilisateur cible

Usage familial, consulté principalement sur téléphone. Pas d'expertise technique requise côté consultation. L'installation initiale est faite une fois par le propriétaire (configuration des sondes Shelly).

### 1.2 Philosophie

Le projet est un **dashboard de lecture** : afficher les données, pas les piloter. Pas de domotique, pas de contrôle d'appareils. Simple, fiable, lisible sur mobile.

Ce que le projet est :
- Un récepteur de données provenant de sondes Shelly H&T Gen3 via webhook HTTP
- Un stockage horodaté des relevés (température + humidité)
- Un dashboard web mobile-first avec temps réel et historique
- Un affichage météo local enrichi (actuel, horaire, J+1) pour Ascain

Ce que le projet n'est pas :
- Un système de domotique ou d'automatisation
- Un système d'alertes (hors périmètre v1)
- Dépendant du cloud Shelly (les sondes poussent directement vers notre serveur)

---

## 2. Stack Technique

| Élément | Choix |
|---|---|
| Hardware sondes | Shelly H&T Gen3 (WiFi, 4×AA ou USB-C) |
| Backend | FastAPI (Python) |
| Base de données | SQLite (fichier unique, évolutif vers InfluxDB si besoin) |
| Frontend | React + Chart.js, mobile-first |
| Hébergement | Serveur dédié OVH (géré par Claude Code) |
| Reverse proxy | Nginx |
| Process manager | systemd |

---

## 3. Modèle de données

```sql
CREATE TABLE sondes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    slug      TEXT NOT NULL UNIQUE,  -- ex: 'chambre-parents', 'salon', 'exterieur'
    nom       TEXT NOT NULL,         -- ex: 'Chambre parents'
    actif     BOOLEAN DEFAULT TRUE  -- false = sonde pas encore achetée/installée, masquée du dashboard
);

CREATE TABLE releves (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sonde_id     INTEGER NOT NULL REFERENCES sondes(id),
    temperature  REAL,               -- °C (nullable : le Shelly H&T Gen3 envoie temp et hum sur deux events distincts)
    humidite     REAL,               -- % HR (nullable : même raison)
    recu_le      TEXT NOT NULL       -- ISO 8601 UTC, ex: 2026-06-01T17:51:05.123456+00:00
);

CREATE INDEX idx_releves_sonde_date ON releves(sonde_id, recu_le);
```

---

## 4. Fonctionnalités

### 4.1 Réception des données (webhook entrant)

Le Shelly H&T Gen3 (firmware HTG3/1.7.5) envoie temp et humidité sur **deux events distincts**
et ne supporte que les URL actions GET. Deux endpoints coexistent :

**Endpoint GET** (utilisé par les sondes Shelly — URL actions) :
```
GET /api/releve/{slug}?temp=${ev.tC}&key=TOKEN   ← event température
GET /api/releve/{slug}?hum=${ev.rh}&key=TOKEN    ← event humidité (action séparée)
```
- `temp` et `hum` sont tous les deux optionnels, mais au moins l'un doit être présent
- La clé API est passée en query param `key`

**Endpoint POST** (usage générique / tests) :
```
POST /api/releve/{slug}
Headers : X-API-Key: TOKEN
Body JSON : { "temp": 21.4, "hum": 58.2 }
```
> **Limite** : `temp` est requis dans le body POST (`ReleverPayload.temp: float`). Un relevé hum-only n'est pas postable via ce endpoint — seul le GET le supporte. Cohérent avec l'usage attendu (POST = tests / intégration externe, GET = sondes Shelly).

Règles métier communes :
- Le `slug` dans l'URL identifie la sonde (ex: `chambre-parents`)
- Si le slug est inconnu → 404
- Le Shelly envoie un relevé si variation ≥ 0,5°C ou 5% humidité, et au maximum toutes les 2h inconditionnellement
- Chaque ligne en base peut contenir temp seule, hum seule, ou les deux
- L'affichage agrège le dernier relevé de temp et le dernier relevé de hum séparément

### 4.2 Dashboard temps réel

Page principale, accessible sans authentification.

Affichage :
- Bloc météo Ascain en tête de page (cf. §4.4)
- Seules les sondes actives (`actif = true`) sont affichées — une sonde pas encore achetée/installée reste en base (table de référence) mais n'apparaît pas sur le dashboard
- Section "Intérieur" : cards pour les sondes intérieures
- Section "Extérieur" : card dédiée pour la sonde extérieure
- Une card par sonde : nom, température actuelle, humidité actuelle, heure du dernier relevé
- Indicateur visuel si sonde hors ligne (pas de relevé depuis > 3h) : badge "Hors ligne" rouge + card pleine largeur
- Responsive mobile-first (cards 2 colonnes sur mobile, intérieur / extérieur séparés visuellement)

Navigation : tap sur une card → vue détail de la sonde (cf. §4.3)

### 4.3 Historique

Vue détail par sonde, accessible par tap sur la card depuis le dashboard.

- Affiche les valeurs actuelles (température + humidité)
- Graphique double-axe : température (axe gauche, ambre) + humidité (axe droit, teal, pointillés)
- Période sélectionnable : 12h / 24h (défaut) / 7 jours / 30 jours
- **Panneau de survol fixe** (entre le sélecteur de période et le graphique) : affiche heure,
  température et humidité du point survolé (souris) ou touché (mobile), toujours les deux
  valeurs ensemble. Au repos (rien sélectionné), affiche en grisé le dernier relevé de la
  période. Une ligne verticale fine dans le graphique repère le point survolé/touché. Sur
  mobile, la valeur reste affichée après `touchend` (pas de retour à l'état repos)
- Bouton retour vers le dashboard

### 4.4 Sondes prévues

| Slug | Nom affiché | Type | Statut (2026-06-20) |
|---|---|---|---|
| `chambre-parents` | Chambre parents | Intérieur | 🔲 Pas encore achetée — en base, `actif=false`, masquée du dashboard |
| `chambre-jade` | Chambre Jade | Intérieur | 🔲 Pas encore achetée — en base, `actif=false`, masquée du dashboard |
| `salon` | Salon | Intérieur | ✅ Installée et active |
| `exterieur` | Extérieur | Extérieur | ✅ Installée et active |

**Démarrage réel avec 1 sonde** (validation hardware), les autres s'ajoutent en base sans changement de code — activer une sonde déjà installée = `UPDATE sondes SET actif = 1`, aucun déploiement nécessaire pour le code (cf. §4.2).

### 4.5 Météo locale Ascain

Bloc météo affiché en tête du dashboard, alimenté par l'API **Open-Meteo** (gratuite, sans clé, open source).

**Coordonnées fixes** : Ascain — lat `43.3667`, lon `-1.5500`

**Structure du bloc (de haut en bas) :**

1. **Conditions actuelles** : température, état du ciel (texte + icône), humidité, vent (vitesse + direction)

2. **Prévisionnel horaire** — bandeau horizontal scrollable, prochaines 24h :
   - Par heure : label heure, icône météo, température, probabilité de précipitations (masquée si < 5%)
   - Heure courante mise en avant visuellement
   - Données source : `hourly=temperature_2m,precipitation_probability,weathercode`

3. **Prévision J+1** : min/max température, état du ciel, mention pluie si probabilité notable

4. ~~**Double modèle** : comparatif AROME vs ECMWF sur la max J+1~~ — **reporté en v2**
   Le paramètre `&models=` retourne des champs préfixés (`temperature_2m_best_match`, etc.)
   incompatibles avec le parsing standard du frontend. Supprimé en v1 (cf. PLAN.md décision 8).

**Appel API :**

```
GET https://api.open-meteo.com/v1/forecast
  ?latitude=43.3667&longitude=-1.5500
  &current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weathercode
  &hourly=temperature_2m,precipitation_probability,weathercode
  &daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode
  &forecast_days=2
  &timezone=Europe/Paris
```

**Cache** : réponse mise en cache 30 min côté backend pour éviter les appels répétés.

---

### 4.6 Vue Analyse (desktop uniquement)

Vue power user accessible via icône `ti-chart-dots-3` dans le header du dashboard
(masquée sur viewport < 768px).

Permet de superposer librement sur un graphique SVG grand format (pleine largeur,
hauteur fluide — cf. plus bas) toute combinaison de :
- Mesures brutes par sonde (température + humidité, 1 couleur par sonde)
- Température Open-Meteo Ascain (comparaison modèle vs sonde réelle)
- Moyennes glissantes 1h et 6h
- Bande min/max journalière
- Histogramme de distribution (mode exclusif, tranches 0.5°C)
- Scatter temp/humidité (mode exclusif, nuage de points)

En mode ligne (courbes), un bouton bascule "Combiné / Séparé" permet de choisir
entre un graphique unique à double axe (température à gauche, humidité à
droite — comportement historique) et deux graphiques empilés à axe unique
(température en haut, humidité en bas), plus lisibles dès que plusieurs
séries sont actives simultanément. Absent en mode histogramme et nuage de
points. Axe X et curseur de survol partagés entre les deux graphiques en
mode séparé. Préférence persistée en localStorage comme les autres réglages
de cette vue.

Une section "Type de mesure" de la barre latérale filtre les courbes par axe :
deux cases "Température" et "Humidité", cochées par défaut toutes les deux.
Décocher un type masque toutes les courbes de cet axe, toutes catégories
confondues (mesures brutes, moyennes glissantes, indices de confort, ΔT,
Open-Meteo, et bande min/max qui est intrinsèquement une donnée de
température). En mode combiné le graphique devient alors mono-axe ; en mode
séparé le panneau correspondant disparaît entièrement. Le filtre est propre au
mode ligne : il est masqué en histogramme et en nuage de points, dont la
sémantique ne dépend pas de ce choix. Préférence persistée en localStorage.

Le graphique est dimensionné sur la carte qui le contient : pleine largeur, et
hauteur occupant l'espace vertical restant jusqu'au bas de la fenêtre, en gardant
visible ce qui le suit (légende) et une marge basse. Planchers de 480px en
hauteur et 600px en largeur pour ne pas l'écraser sur petite fenêtre ; recalcul
au redimensionnement, sans rechargement. En mode séparé, la hauteur disponible
est partagée entre les panneaux actifs — et le panneau restant prend toute la
hauteur si un seul type de mesure est coché.

Plage temporelle : boutons rapides (12h, 24h, 7j, 30j, 90j, 1 an) +
date pickers libres "Du / Au". Les deux mécanismes sont exclusifs.

Légende explicative dynamique sous le graphique (visible uniquement si au moins
une case cochée, contenu adapté aux cases actives).

Préférences (cases cochées + dernière plage) persistées en localStorage.

---

## 5. Charte graphique & UI Template

### 5.1 Ambiance

Chaud et domestic. Tons crème/sable, convivial, sans être chargé.

| Élément | Valeur |
|---|---|
| Fond général | `#F7F3EE` (crème chaud) |
| Fond cards | `#FFF9F2` (blanc cassé) |
| Fond sections / météo | `#EDE6DB` (sable) |
| Accent température | `#BA7517` / `#EF9F27` (ambre) |
| Accent humidité | `#1D9E75` (teal) |
| Accent pluie | `#378ADD` (bleu) |
| Erreur / hors ligne | `#A32D2D` / `#FCEBEB` (rouge) |
| Texte principal | `#1A1714` |
| Texte secondaire | `#6B6560` |
| Texte tertiaire / timestamps | `#B5B0A8` |

### 5.2 Navigation

- Une seule page (pas de routing)
- Dashboard par défaut
- Tap card sonde → vue détail avec historique (animation retour via bouton)

### 5.3 Maquette de référence

Fichier `maison-temp-mockup.html` — validée le 2026-05-23. Constitue la référence visuelle pour l'implémentation des LOTs 2 et 3.

---

## 6. Sécurité / Auth / Compliance

- Endpoint `/api/releve/{slug}` protégé par `X-API-Key` (token généré à l'install, stocké dans `.env`)
- Dashboard en lecture seule, pas d'authentification nécessaire en v1 (réseau familial, données non sensibles)
- HTTPS via certificat Let's Encrypt (Nginx)
- Pas de données personnelles collectées

---

## 7. Déploiement & Production

- Serveur OVH dédié, géré par Claude Code
- Process : `systemd` service `maison-temp.service`
- Nginx reverse proxy → FastAPI sur port local (ex: 8042)
- Sous-domaine : `meteo.domaine.fr` (domaine principal à confirmer)
- Mise à jour : `git pull` + `systemctl restart maison-temp`
- Logs : `journalctl -u maison-temp`

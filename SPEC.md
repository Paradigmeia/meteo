# SPEC.md — maison-temp

**Version** : 1.0
**Date** : 2026-05-23
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
    actif     BOOLEAN DEFAULT TRUE
);

CREATE TABLE releves (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sonde_id     INTEGER NOT NULL REFERENCES sondes(id),
    temperature  REAL NOT NULL,      -- °C
    humidite     REAL,               -- % HR (nullable, Shelly envoie toujours les deux)
    recu_le      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_releves_sonde_date ON releves(sonde_id, recu_le);
```

---

## 4. Fonctionnalités

### 4.1 Réception des données (webhook entrant)

Chaque Shelly H&T Gen3 est configuré pour appeler une URL à chaque relevé :

```
POST /api/releve/{slug}
Body JSON : { "temp": 21.4, "hum": 58.2 }
```

Règles métier :
- Le `slug` dans l'URL identifie la sonde (ex: `chambre-parents`)
- Si le slug est inconnu → 404
- La sonde Shelly envoie un relevé si variation ≥ 0,5°C ou 5% humidité, et au maximum toutes les 2h inconditionnellement
- Un token d'authentification simple (header `X-API-Key`) protège l'endpoint

### 4.2 Dashboard temps réel

Page principale, accessible sans authentification.

Affichage :
- Une carte par sonde : nom, température actuelle, humidité actuelle, heure du dernier relevé
- Indicateur visuel si sonde hors ligne (pas de relevé depuis > 3h)
- Responsive mobile-first (cards empilées sur mobile, grille sur desktop)

### 4.3 Historique

Par sonde, graphique de la température et de l'humidité sur une période sélectionnable :
- 24 dernières heures (défaut)
- 7 jours
- 30 jours

### 4.4 Sondes prévues

| Slug | Nom affiché | Type |
|---|---|---|
| `chambre-parents` | Chambre parents | Intérieur |
| `chambre-jade` | Chambre Jade | Intérieur |
| `salon` | Salon | Intérieur |
| `exterieur` | Extérieur | Extérieur |

**Démarrage réel avec 1 sonde** (validation hardware), les 3 autres s'ajoutent en base sans changement de code.

---

## 5. Sécurité / Auth / Compliance

- Endpoint `/api/releve/{slug}` protégé par `X-API-Key` (token généré à l'install, stocké dans `.env`)
- Dashboard en lecture seule, pas d'authentification nécessaire en v1 (réseau familial, données non sensibles)
- HTTPS via certificat Let's Encrypt (Nginx)
- Pas de données personnelles collectées

---

## 6. Déploiement & Production

- Serveur OVH dédié, géré par Claude Code
- Process : `systemd` service `maison-temp.service`
- Nginx reverse proxy → FastAPI sur port local (ex: 8042)
- Sous-domaine : `meteo.domaine.fr` (domaine principal à confirmer)
- Mise à jour : `git pull` + `systemctl restart maison-temp`
- Logs : `journalctl -u maison-temp`

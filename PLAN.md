# PLAN.md — maison-temp

**Version** : 1.0
**Date** : 2026-05-23
**Référence** : SPEC.md v1.0

---

## 1. Arborescence du projet

```
maison-temp/
├── backend/
│   ├── main.py            # FastAPI app, routes
│   ├── database.py        # SQLite init, helpers
│   ├── models.py          # Pydantic schemas
│   ├── config.py          # Settings (env vars)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── SondeCard.jsx      # Carte temps réel
│   │   │   └── HistoriqueChart.jsx # Graphique Chart.js
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── nginx/
│   └── maison-temp.conf   # Config Nginx
├── maison-temp.service    # Systemd unit
├── .env.example
├── SPEC.md
├── PLAN.md
└── PROJECT.md
```

---

## 2. Dépendances

**Backend (Python)**
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-dotenv==1.0.1
aiosqlite==0.20.0
```

**Frontend (Node)**
```json
{
  "react": "^18.3.0",
  "chart.js": "^4.4.0",
  "react-chartjs-2": "^5.2.0",
  "vite": "^5.4.0"
}
```

---

## 3. Configuration

**`.env` (à créer depuis `.env.example`)**
```
API_KEY=<token_genere>
DATABASE_PATH=/var/lib/maison-temp/db.sqlite
```

**Variables d'environnement Shelly** : l'URL webhook à configurer dans l'app Shelly pour chaque sonde :
```
https://meteo.domaine.fr/api/releve/{slug}
Header: X-API-Key: <token>
```

---

## 4. Schéma de base de données

Voir SPEC.md §3 (source de vérité).

---

## 5. Décisions techniques

### Décision 1 (2026-05-23)

- **Contexte** : Choix du hardware sonde
- **Choix** : Shelly H&T Gen3 (WiFi, 4×AA ou USB-C)
- **Pourquoi** : ESP8266 DIY déjà testé et jugé instable. Shelly = plug & play, webhook HTTP natif, pas de hub requis, ~20€/unité, autonomie 1 an sur piles.
- **Trade-off** : Pas de batterie rechargeable intégrée → utiliser des AA rechargeables (Eneloop) ou brancher en USB-C.

### Décision 2 (2026-05-23)

- **Contexte** : Choix de la base de données
- **Choix** : SQLite au démarrage
- **Pourquoi** : Zéro infra, fichier unique, suffisant pour 4 sondes avec des relevés toutes les quelques minutes. Migration vers InfluxDB possible si les volumes grossissent ou si on veut du time-series avancé.
- **Trade-off** : Pas de rétention automatique des données anciennes (à implémenter si besoin).

### Décision 3 (2026-05-23)

- **Contexte** : Authentification du dashboard
- **Choix** : Dashboard en lecture libre, seul l'endpoint webhook est protégé (X-API-Key)
- **Pourquoi** : Données non sensibles, usage familial. Simplifier l'accès mobile.
- **Trade-off** : Données lisibles par quiconque connaît l'URL. Acceptable en v1.

### Décision 4 (2026-05-23)

- **Contexte** : Déploiement avec 1 sonde pour validation
- **Choix** : Le code gère N sondes dès le départ (table `sondes` en base), mais on démarre avec 1 sonde physique.
- **Pourquoi** : Éviter une refacto quand on achète les 3 sondes suivantes. Ajouter une sonde = INSERT en base uniquement.
- **Trade-off** : Aucun.

### Décision 5 (2026-05-23)

- **Contexte** : Choix de la source météo externe pour Ascain
- **Choix** : Open-Meteo (gratuit, sans clé API, open source)
- **Pourquoi** : Agrège 30+ modèles dont AROME (Météo-France, 1-2 km pour la France) et ECMWF IFS. Pays Basque = terrain complexe (montagne + côte) → résolution 1-2 km essentielle. Zéro coût, zéro dépendance à un compte tiers.
- **Trade-off** : Pas de SLA garanti (usage non-commercial). Acceptable pour un usage domestique. Mitigation : cache 30 min côté serveur, fallback gracieux si l'API est indisponible.

--- (historique)

_(vide pour l'instant)_

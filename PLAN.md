# PLAN.md — maison-temp

**Version** : 1.2
**Date** : 2026-06-20
**Référence** : SPEC.md v1.2

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
│   │   │   ├── MeteoCard.jsx          # Bloc météo complet (actuel + horaire + J+1)
│   │   │   ├── HourlyStrip.jsx        # Bandeau horaire scrollable
│   │   │   ├── SondeCard.jsx          # Card sonde temps réel
│   │   │   ├── HistoriqueChart.jsx    # Graphique Chart.js dual-axe
│   │   │   ├── AnalyseView.jsx        # Vue Analyse complète (desktop)
│   │   │   └── AnalyseChart.jsx       # Graphique SVG multi-courbes
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── nginx/
│   └── maison-temp.conf
├── docs/
│   └── ui-mockup.html     # ⬅ RÉFÉRENCE UI — ouvrir dans un navigateur avant d'implémenter
├── maison-temp.service
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

Variables d'environnement (`.env`) :

```
API_KEY=<token généré à l'install>
DATABASE_PATH=./data/maison.db
PORT=8042
```

---

## 4. Schéma de base de données

Cf. SPEC.md §3 — schéma SQL complet.

---

## 5. Référence UI

**Fichier** : `docs/ui-mockup.html`

Maquette interactive HTML validée le 2026-05-23. À ouvrir dans un navigateur (mode responsive 390px) avant d'implémenter les LOTs 2 et 3.

Ce que la maquette montre et que le code doit reproduire :
- Charte couleurs complète (variables CSS dans SPEC.md §5.1)
- Structure dashboard : météo en tête → intérieur (2 col) → extérieur (pleine largeur)
- État hors ligne : badge rouge + card pleine largeur + icône wifi-off
- Bloc météo : actuel + bandeau horaire scrollable + J+1 + double modèle AROME/ECMWF
- Vue détail sonde : métriques actuelles + sélecteur période + graphique dual-axe
- Navigation : tap card → détail, bouton retour

---

## 6. Décisions techniques

### Décision 1 (2026-05-23)

- **Contexte** : Choix du hardware sonde
- **Choix** : Shelly H&T Gen3
- **Pourquoi** : WiFi natif, webhook HTTP sans cloud Shelly, plug & play, ~20€/unité
- **Trade-off** : Pas IP-certifié extérieur → boîtier abrité nécessaire pour la sonde extérieure

### Décision 2 (2026-05-23)

- **Contexte** : Base de données
- **Choix** : SQLite au départ
- **Pourquoi** : Zéro infra, fichier unique, suffisant pour 4 sondes à relevé toutes les ~10min
- **Trade-off** : Migration InfluxDB possible si besoin de requêtes temporelles avancées

### Décision 3 (2026-05-23)

- **Contexte** : Auth dashboard
- **Choix** : Pas d'auth en v1 (lecture seule)
- **Pourquoi** : Usage familial réseau local, données non sensibles. Simplifie l'accès mobile.
- **Trade-off** : Données lisibles par quiconque connaît l'URL. Acceptable en v1.

### Décision 4 (2026-05-23)

- **Contexte** : Déploiement avec 1 sonde pour validation
- **Choix** : Le code gère N sondes dès le départ (table `sondes` en base), mais on démarre avec 1 sonde physique.
- **Pourquoi** : Éviter une refacto quand on achète les 3 sondes suivantes. Ajouter une sonde = INSERT en base uniquement.
- **Trade-off** : Aucun.

### Décision 5 (2026-05-23)

- **Contexte** : API météo
- **Choix** : Open-Meteo, double modèle AROME (`best_match`) + ECMWF IFS (`ecmwf_ifs025`)
- **Pourquoi** : Gratuit, sans clé API, open source (CC BY 4.0). AROME = résolution 1-2 km pour la France. Comparatif des deux modèles = indicateur de confiance visible.
- **Trade-off** : Dépendance externe non maîtrisée. Cache 30min pour limiter l'impact d'une indisponibilité.

### Décision 6 (2026-06-01)

- **Contexte** : Intégration réelle du Shelly H&T Gen3 (firmware HTG3/1.7.5)
- **Choix** : Endpoint GET `POST /api/releve/{slug}` complété par `GET /api/releve/{slug}?temp=X&hum=Y&key=TOKEN`
- **Pourquoi** : Le firmware Shelly ne supporte que les URL actions GET, et envoie temp et humidité sur deux events distincts. La variable humidité est `${ev.rh}` (relative humidity) — `${ev.h}` est null dans tous les events. Solution : deux actions Shelly séparées ("Changement de température" / "Changement d'humidité"), `temp` et `hum` optionnels en query param.
- **Trade-off** : La clé API est dans l'URL (visible dans les logs Nginx). Acceptable pour usage domestique — le dashboard est déjà en lecture libre.

### Décision 7 (2026-06-01)

- **Contexte** : Schéma de la table `releves` face aux events séparés Shelly
- **Choix** : `temperature` et `humidite` sont toutes deux `NULLABLE` en base
- **Pourquoi** : Chaque event Shelly ne porte qu'une valeur. Forcer `NOT NULL` sur `temperature` bloquait les inserts hum-only. L'affichage (backend `/api/sondes` et frontend `Detail.jsx`) agrège le dernier temp et la dernière hum séparément.
- **Trade-off** : Requêtes légèrement plus complexes (deux LEFT JOIN ou deux `.find()` au lieu d'un). Négligeable à l'échelle de ce projet.

### Décision 8 (2026-06-01)

- **Contexte** : Paramètre `&models=` dans l'URL Open-Meteo
- **Choix** : Suppression du paramètre `&models=best_match,ecmwf_ifs025`
- **Pourquoi** : Avec ce paramètre, l'API retourne les champs préfixés (`temperature_2m_best_match`, etc.) au lieu des noms standard (`temperature_2m`). Le frontend ne gérait pas ces préfixes → données météo manquantes.
- **Trade-off** : La comparaison AROME vs ECMWF (badge "Accord/Divergentes") n'est plus disponible en v1. Peut être réactivée en v2 avec parsing dédié.

### Décision 9 (2026-06-20)

- **Contexte** : `chambre-parents` et `chambre-jade` sont en base depuis le LOT 1 (sondes prévues mais pas encore achetées) et s'affichaient sur le dashboard avec "Aucune donnée" / badge "Hors ligne" permanent
- **Choix** : `GET /api/sondes` filtre désormais sur `actif = 1` — le champ `actif` était stocké depuis le LOT 1 mais jamais exploité par le frontend
- **Pourquoi** : Une sonde non achetée ne doit pas apparaître sur le dashboard familial. Activer une sonde déjà en base quand le hardware est installé = `UPDATE sondes SET actif = 1`, sans déploiement de code (cf. décision 4)
- **Trade-off** : Aucun changement de comportement pour les sondes déjà actives. Nécessite un redéploiement (`scripts/update.sh`) pour que ce filtre prenne effet, contrairement à un simple flip de `actif` qui lui ne demande rien

### Décision 10 (2026-06-20)

- **Contexte** : Vue expert desktop avec de nombreuses séries de données simultanées (issue #19)
- **Choix** : Calculs (moyennes glissantes, Heat Index, point de rosée) effectués
  côté frontend à partir des données brutes reçues de l'API
- **Pourquoi** : Évite de multiplier les endpoints backend ; les volumes de données
  sur les plages courtes (12h-7j) sont compatibles avec un calcul JS ; backend
  reste simple et non couplé aux préférences UI
- **Trade-off** : Sur 90j/1an avec 4 sondes, le volume de points peut être élevé.
  Si perf insuffisante, migrer les calculs côté backend en v2.

---

## 7. Décisions abandonnées (historique)

*(vide pour l'instant)*

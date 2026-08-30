# PLAN.md — maison-temp

**Version** : 1.15
**Date** : 2026-08-30
**Référence** : SPEC.md v1.9

---

## 1. Arborescence du projet

```
maison-temp/
├── backend/
│   ├── main.py            # FastAPI app, routes
│   ├── database.py        # SQLite init, helpers
│   ├── models.py          # Pydantic schemas
│   ├── config.py          # Settings (env vars)
│   ├── test_main.py       # Tests pytest du backend
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── App.css / index.css
│   │   ├── meteoUtils.js              # Libellés et icônes des codes météo Open-Meteo
│   │   ├── components/
│   │   │   ├── Icon.jsx               # Rend une icône Tabler (+ Icon.test.js)
│   │   │   ├── Dashboard.jsx          # Écran d'accueil mobile (météo + cartes sondes)
│   │   │   ├── Detail.jsx             # Vue détail d'une sonde (mobile)
│   │   │   ├── MeteoCard.jsx          # Bloc météo complet (actuel + horaire + J+1)
│   │   │   ├── SondeCard.jsx          # Card sonde temps réel
│   │   │   ├── HistoriqueChart.jsx    # Graphique SVG dual-axe (vue Détail mobile)
│   │   │   ├── SurvolPanel.jsx        # Panneau de valeurs au survol
│   │   │   ├── AnalyseView.jsx        # Vue Analyse complète (desktop)
│   │   │   └── AnalyseChart.jsx       # Graphique SVG multi-courbes
│   │   ├── hooks/
│   │   │   ├── useSondes.js           # Sondes + valeurs courantes (polling)
│   │   │   ├── useReleves.js          # Relevés d'une sonde (vue Détail)
│   │   │   ├── useAnalyseReleves.js   # Relevés multi-sondes (Vue Analyse)
│   │   │   ├── useMeteo.js            # Météo Open-Meteo via le backend
│   │   │   └── useIsDesktop.js        # Bascule mobile / desktop
│   │   └── utils/
│   │       ├── iconPaths.js           # Tracés SVG des 15 icônes Tabler embarquées
│   │       ├── chartUtils.js          # Échelles, graduations, lissage, géométrie curseur→viewBox
│   │       ├── chartUtils.test.js     # Tests vitest de la géométrie curseur→viewBox
│   │       └── analyseUtils.js        # Helpers propres à la Vue Analyse
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── scripts/
│   ├── install.sh
│   └── update.sh
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
  "react": "^19.2.6",
  "react-dom": "^19.2.6",
  "vite": "^8.0.12",
  "vitest": "^4.1.11"
}
```
Aucune dépendance chargée depuis un CDN : les icônes sont embarquées en SVG
(décision 15). Les graphiques sont dessinés en SVG à la main, sans librairie
(cf. décision 10).
`vitest` est une devDependency ; `npm test` lance la suite (décision 14).

---

## 3. Configuration

Variables d'environnement (`.env`) :

```
API_KEY=<token généré à l'install>
DATABASE_PATH=./data/maison.db
PORT=8042
```

### Règle sudo (hors dépôt)

`/etc/sudoers.d/maison-temp`, en `0440`, posée par `scripts/install.sh`. Sur
cette machine :

```
debian ALL=(root) NOPASSWD: /usr/bin/systemctl restart maison-temp
```

Le chemin n'est pas figé dans le script : il est cherché dans les répertoires
système au moment de l'installation, `sudo` résolvant la commande via son
`secure_path` et non via le `PATH` de l'utilisateur.

Elle existe pour que `scripts/update.sh` aille jusqu'au bout hors terminal
interactif. Cf. décision 20 pour la portée exacte de la concession et les
raisons de la forme retenue.

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
- **Trade-off** : La clé API est dans l'URL (visible dans les logs Nginx). Acceptable pour usage domestique — le dashboard est déjà en lecture libre. *Révisé le 2026-08-30 : la fuite s'étendait aussi au journal systemd via uvicorn, et l'ampleur mesurée a fait revoir ce « acceptable » — cf. décision 17 et issue #35.*

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

> **Note (2026-08-24)** : la partie Heat Index / point de rosée de cette décision
> ne s'applique plus — fonctionnalité retirée (jugée inutilisée à l'usage, cf.
> issue #28). Le choix de calcul frontend reste valable pour les moyennes
> glissantes, et le trade-off de volume ci-dessus s'en trouve allégé : deux
> séries dérivées de moins par sonde cochée (Heat Index et point de rosée),
> plus une série globale (ΔT).

### Décision 11 (2026-07-04)

- **Contexte** : Vue Analyse — le graphique combiné à double axe devient
  difficile à lire dès que plusieurs séries température (brutes, moyennes
  glissantes, indices de confort, ΔT, Open-Meteo) sont actives en même temps
  que l'humidité
- **Choix** : Bouton bascule "Combiné / Séparé" (`AnalyseChart.jsx`,
  `AnalyseView.jsx`) — en mode séparé, deux graphiques empilés à axe unique
  remplacent le graphique double-axe ; axe X et curseur de survol partagés
- **Pourquoi** : Un graphique à deux échelles superposées oblige à interpréter
  visuellement quelle courbe se rapporte à quel axe ; deux graphiques à axe
  unique lèvent l'ambiguïté sans rien perdre de l'alignement temporel
- **Trade-off** : Légèrement plus de hauteur totale à l'écran en mode séparé
  (deux graphiques de 220px + espacement, contre 480px en mode combiné).
  L'humidité brute perd son style pointillé en mode séparé (redevient un
  trait plein, plus besoin de la distinguer visuellement de la température
  puisqu'elle est sur son propre graphique)

### Décision 12 (2026-08-24)

- **Contexte** : Vue Analyse — la hauteur du graphique était une constante
  module (`H = 480` dans `AnalyseChart.jsx`), alors que la vue est desktop-only
  et laisse souvent 200 à 400px de vide sous la carte graphique. Par ailleurs,
  rien ne permettait de n'afficher que la température ou que l'humidité
- **Choix** : (a) Les dimensions sont mesurées par `AnalyseView`
  (`useLayoutEffect` + écouteur `resize`) et passées en props `width`/`height` à
  `AnalyseChart`, dont le `viewBox` les reprend telles quelles ; planchers
  `MIN_CHART_HEIGHT = 480` et `MIN_CHART_WIDTH = 600`.
  (b) Nouvelle section "Type de mesure" dans la barre latérale ; le filtrage se
  fait en amont sur `lines`/`bands` dans `AnalyseView`, `AnalyseChart` recevant
  en plus `showTemp`/`showHum` pour savoir combien de panneaux rendre en mode
  séparé. La hauteur d'un panneau vaut `(height - séparateur) / 2` à deux
  panneaux, `height` à un seul
- **Pourquoi** : Mesurer plutôt que bumper la constante — un simple `H = 700`
  aurait cassé les résolutions basses (1366×768) et serait resté faux sur les
  écrans hauts. Filtrer en amont plutôt que dans `AnalyseChart` garde le
  composant de rendu ignorant des préférences utilisateur : le mode combiné
  devient mono-axe sans aucun cas particulier, puisque l'échelle de l'axe
  décoché se retrouve simplement vide
- **Corollaire (largeur)** : le `viewBox` avait jusqu'ici une largeur figée
  (`W = 900`) pour une largeur CSS de 100%. Le `preserveAspectRatio` par défaut
  (`xMidYMid meet`) mettait donc le dessin à l'échelle `min(largeurCarte / 900, 1)` :
  bandes blanches latérales sur carte plus large, et — plus gênant une fois la
  hauteur devenue fluide — letterboxing vertical sur carte plus étroite, qui
  aurait mangé une partie de la hauteur gagnée. Reprendre la largeur mesurée met
  l'échelle à exactement 1 dans les deux sens ; le graphique devient enfin pleine
  largeur, ce que visait la décision de layout de l'issue #21
- **Trade-off** : La mesure raisonne en coordonnées document
  (`getBoundingClientRect().top + scrollY`) pour ne pas dépendre du défilement,
  et déduit la hauteur de ce qui suit la carte (légende, marge basse) afin de ne
  pas repousser la légende hors de l'écran. Changer la hauteur du graphique ne
  déplaçant pas le haut de la carte, il n'y a pas de boucle de rétroaction ; un
  `ResizeObserver` sur la carte en aurait créé une

### Décision 13 (2026-08-24)

- **Contexte** : `temp: float` acceptait `NaN` et `±inf` (comportement Pydantic
  par défaut), et `_parse_shelly_value` faisait un `float()` nu. Une valeur non
  finie stockée faisait échouer la sérialisation JSON de la **réponse entière**,
  pas seulement de la ligne fautive — donc 500 sur `/api/releves` comme sur
  `/api/sondes`, et côté frontend un graphique ou un dashboard vide sans le
  moindre message (issue #36)
- **Choix** : Garde-fou des deux côtés plutôt que d'un seul.
  (a) **À l'écriture** : bornes `allow_inf_nan=False` + `ge`/`le` sur
  `ReleverPayload`, contrôle de finitude et de bornes dans `_parse_shelly_value`.
  (b) **À la lecture** : `_finite_or_none` neutralise une valeur non finie lue en
  base en la traitant comme une mesure absente, sur les trois chemins de lecture
  (`/api/sondes`, `/api/releves` brut, `/api/releves` agrégé)
- **Pourquoi** : Les bornes seules ne suffisent pas — elles n'assainissent pas les
  lignes écrites avant elles, et rien ne permet de purger une ligne depuis
  l'application. La tolérance en lecture seule ne suffit pas non plus : elle
  laisserait entrer des données aberrantes qui écraseraient l'échelle des
  graphiques. Le coût de la seconde est négligeable (un `math.isfinite` par
  valeur) et elle transforme une panne totale en un point manquant
- **Gestionnaire de `RequestValidationError`** : le gestionnaire par défaut de
  FastAPI recopie l'entrée rejetée dans le corps du 422. Quand cette entrée est
  non finie, `json.dumps` lève et le client reçoit un 500 opaque — la validation
  faisait son travail, c'est son compte rendu qui cassait. Un gestionnaire dédié
  remplace les non-finis par leur écriture texte
- **Trade-off** : Une ligne non finie déjà en base devient une mesure absente
  sans être signalée — un point parmi des centaines sur `/api/releves`, mais la
  valeur courante de la sonde sur `/api/sondes`, jusqu'au prochain relevé sain.
  C'est le même traitement qu'un relevé qui ne porte pas la grandeur, et le cas
  est désormais impossible à créer. Vérifié sur la base de production : 0 ligne
  non finie sur 7478 au moment du correctif
- **Humidité écrêtée, température rejetée** : traitement volontairement
  dissymétrique. Le Shelly n'émet qu'une fois et ne réémet pas sur erreur, donc
  un 422 perd le relevé définitivement. Une humidité à 100,2 % est une
  imprécision de capteur en condensation, pas une aberration : on l'écrête dans
  une marge de 5 points. Les bornes de température (-100..100 °C) sont si larges
  qu'un dépassement ne peut pas être une imprécision — le rejet reste correct
- **Note SQLite** : SQLite n'a pas de représentation pour `NaN` et le stocke en
  `NULL` — un `NaN` se traduisait donc par une mesure perdue, pas par une ligne
  empoisonnée. C'est `±inf` qui fait l'aller-retour intact et constituait le vrai
  vecteur. Consigné par un test, l'hypothèse étant portante pour le correctif

### Décision 14 (2026-08-29)

- **Contexte** : la conversion « position du pointeur → abscisse dans le repère
  du `viewBox` » existait en deux exemplaires. Celui d'`AnalyseChart` a été
  corrigé par #29 (passage par `getScreenCTM()`), celui d'`HistoriqueChart` a
  gardé la règle de trois sur `getBoundingClientRect()`. Duplication assumée
  avant #29, divergence depuis : deux calculs pour un même problème, dont un
  connu comme faux dès qu'il y a letterboxing (issue #30)
- **Choix** : géométrie extraite dans `utils/chartUtils.js` en trois fonctions —
  `viewBoxXFromClient` (conversion par la matrice), `viewBoxXFromRect` (son
  équivalent arithmétique pour le `preserveAspectRatio` par défaut), et
  `viewBoxXFromPointerEvent` qui compose les deux pour un évènement React. Les
  deux composants consomment cette dernière
- **Matrice d'abord, boîte en repli** : la matrice est exacte quelle que soit la
  transformation appliquée au dessin ; le calcul par la boîte ne l'est que pour
  le `preserveAspectRatio` par défaut, ce qui est le cas des deux graphiques. Il
  sert quand la matrice est indisponible (svg non rendu) et rend la géométrie
  testable sans DOM
- **Projection écrite à la main** plutôt que déléguée à `DOMPoint` : `x' = a·x +
  c·y + e` est la ligne utile du produit matriciel 2D. La fonction devient de
  l'arithmétique pure, testable hors navigateur — `DOMPoint` n'existe pas sous
  Node. Les CTM d'un `<svg>` sont toujours 2D, la perspective n'a pas à être
  traitée
- **Dimensions du `viewBox` lues sur l'élément** (`svg.viewBox.baseVal`) et non
  passées par l'appelant : en mode Séparé, `AnalyseChart` attache les mêmes
  gestionnaires à deux panneaux de hauteurs différentes — un paramètre pourrait
  diverger de la géométrie réellement rendue, `baseVal` non
- **Effet sur la vue Détail** : aucun aujourd'hui. `HistoriqueChart` a un
  `viewBox` de 360 de large sous une shell capée à 390px, donc la largeur rendue
  reste sous 360 : sans letterboxing, ancien et nouveau calcul coïncident (pinné
  par un test). Le jour où la vue Détail s'élargit, le bug #26 ne réapparaît plus
- **`vitest` introduit à cette occasion** : le frontend n'avait aucun runner, là
  où le backend a `test_main.py`. La non-régression de #26 reposait entièrement
  sur la relecture — faible pour un bug qui lui avait justement échappé. La
  géométrie une fois pure se teste sans DOM ni jsdom, donc sans autre dépendance
  que `vitest` lui-même

### Décision 15 (2026-08-29)

- **Contexte** : `index.html` chargeait la feuille de style `@tabler/icons-webfont`
  depuis jsdelivr, sans `integrity` ni `crossorigin`. Une compromission du CDN
  aurait permis d'injecter du CSS arbitraire sur tout le site, et aucune CSP ne
  rattrapait le coup (issue #50, et #49 pour la CSP)
- **Choix** : supprimer le CDN plutôt que le sécuriser. Les 15 glyphes utilisés
  sont embarqués en SVG dans `utils/iconPaths.js`, tracés repris du dépôt Tabler
  3.19.0 (MIT), et rendus par `components/Icon.jsx` — données et composant
  séparés, un fichier de composant qui exporte autre chose qu'un composant
  cassant le Fast Refresh de Vite
- **Pourquoi pas SRI** : `integrity` n'aurait couvert que la feuille, pas les
  fichiers de police qu'elle tire ensuite en relatif — SRI n'existe pas pour les
  `url()` d'un CSS. Et la disproportion restait : 238 kB de CSS plus 865 kB de
  woff2 — ~900 kB de transfert réel — pour quinze glyphes. Le bundle applicatif
  entier en fait 228 non compressés
- **Coût réel** : +3,0 kB de bundle (228,6 → 231,6 kB), contre ~900 kB qui ne
  transitent plus, une résolution DNS et une poignée de main TLS vers un tiers en
  moins au chargement, et les deux exceptions `cdn.jsdelivr.net` de la CSP de #49
  qui disparaissent — celle-ci se réduit à `'self'`. Le trafic évité se compte en
  transfert réel : jsdelivr sert la feuille en gzip (38 kB, non 238), le woff2 de
  865 kB étant déjà compressé
- **Rendu en `1em` et `currentColor`** : le composant reprend le comportement
  d'un glyphe de police, donc les `style={{ fontSize, color }}` déjà écrits dans
  les composants et la règle `.hour-icon` d'App.css continuent de s'appliquer
  sans être touchés. Seul ajout CSS : `.icon { vertical-align: -0.1em }`, un
  `<svg>` inline ne se posant pas sur la ligne de base comme un glyphe — valeur
  dérivée du descent de la police remplacée (100/1000 em), pas une heuristique
- **Bug découvert au passage** : `ti-cloud-sun` et `ti-cloud-drizzle` n'existent
  pas dans Tabler 3.19.0. « Partiellement nuageux » (WMO 2) et « Bruine »
  (51/53/55) n'affichaient donc **aucune icône** en production, sans erreur
  console ni trace serveur. Remplacés par `haze` et `droplets`. Un nom d'icône
  qui ne résout rien étant silencieux par nature, `Icon.test.js` vérifie
  désormais que tout nom référencé existe, et qu'aucune icône n'est embarquée
  sans être utilisée

### Décision 16 (2026-08-29)

- **Contexte** : le site ne servait que `X-Robots-Tag` et un `Strict-Transport-Security`
  sans `includeSubDomains`. Ni CSP, ni `X-Content-Type-Options`, ni
  `Referrer-Policy`, ni protection contre l'inclusion en iframe (issue #49)
- **Ce que ça vaut ici** : peu de chose aujourd'hui, et c'est assumé. Le
  dashboard n'a pas d'authentification et n'affiche que des températures : pas de
  session à voler, pas d'action privilégiée à déclencher. L'intérêt est d'être le
  filet qui rattraperait une ressource tierce compromise, et de rendre sûre par
  défaut l'authentification prévue en v2 plutôt que de la sécuriser après coup
- **Politique** : `'self'` partout, rendu possible par la PR #51 qui a supprimé
  la dernière ressource tierce. Plus `frame-ancestors 'none'`, `base-uri 'none'`,
  `form-action 'none'`, `object-src 'none'`
- **Aucune exception**, contrairement à ce que l'issue #49 annonçait. Elle
  supposait qu'il faudrait `style-src-attr 'unsafe-inline'` pour les 43
  `style={{ … }}` des composants. C'est faux : React applique ces styles par le
  CSSOM (`style.setProperty`), pas par `setAttribute('style', …)`. L'attribut
  apparaît dans le DOM mais n'a jamais été « posé », et la CSP ne contrôle que la
  pose. Vérifié sous Chromium avec la politique la plus stricte : les trois vues
  s'affichent, `display: flex` et `font-size: 22px` inline s'appliquent, zéro
  violation. Le `'unsafe-inline'` initialement prévu était donc gratuit — et
  c'était la seule ouverture de toute la politique
- **Piège en aval, `img-src` sans `data:`** : Vite inline en data-URI tout asset
  importé de moins de 4 ko (`assetsInlineLimit`). La première image légère
  ajoutée serait bloquée sans qu'aucune URL n'apparaisse dans le code source
- **`form-action 'none'` et la v2** : la directive ne retombe pas sur
  `default-src`. L'authentification prévue en v2 — l'argument qui justifie cette
  décision — devra l'assouplir si elle passe par un `<form method="post">`
  plutôt que par `fetch`
- **Effet de bord de `nosniff`** : `try_files` renvoie `index.html` en 200
  `text/html` pour tout asset manquant. Le navigateur refuse désormais de
  l'exécuter au lieu d'échouer sur une erreur de syntaxe — plus lisible, mais le
  message change en cas de cache portant un `index.html` périmé
- **`X-Frame-Options` en plus de `frame-ancestors`** : double emploi assumé, pour
  les navigateurs qui ignorent CSP niveau 2
- **Piège nginx consigné dans le fichier** : `add_header` n'est pas cumulatif. Un
  `add_header` posé dans un bloc `location` annule **tous** ceux hérités du bloc
  `server`. Aucun `location` n'en pose aujourd'hui, mais le jour où l'un le fera,
  la CSP disparaîtra silencieusement de ces réponses
- **Vérifié sans toucher la production** : la configuration a été lancée dans une
  instance nginx de test sur un port haut, certificat auto-signé, servant le vrai
  `dist/`. Les six en-têtes relevés sur `/` comme sur `/api/` (héritage confirmé),
  puis les trois vues parcourues sous Chromium (Playwright) — zéro violation CSP,
  zéro erreur console, zéro requête échouée, 31 icônes rendues aux bonnes tailles.
  Vérifié aussi que Cloudflare, devant ce site, n'injecte aucun script
  (`cdn-cgi`, Rocket Loader) et ne pose pas de CSP concurrente — deux CSP
  s'intersectent, ce qui produit des blocages difficiles à diagnostiquer
- **Déploiement manuel** : `scripts/update.sh` ne déploie pas la configuration
  nginx, seul `install.sh` le fait. Après merge :
  `cd /home/debian/meteo && git pull origin main` (le checkout de production n'a
  pas encore le fichier), puis
  `sudo cp /home/debian/meteo/nginx/maison-temp.conf /etc/nginx/sites-available/maison-temp && sudo nginx -t && sudo systemctl reload nginx`

### Décision 17 (2026-08-30)

- **Contexte** : la décision 6 assumait que la clé d'API soit visible dans les
  logs nginx. La mesure a montré que ce « acceptable » reposait sur une
  sous-estimation. Trois mesures :
  - **8 243 lignes** portant la clé dans `access.log`. Et ce fichier n'est
    **jamais tourné** : `/etc/logrotate.d/nginx` déclare bien `daily` et
    `rotate 14`, mais aucune unité `logrotate.timer` n'existe sur cette machine
    et `/var/log/nginx/` ne contient aucune archive. Le fichier est continu du
    8 mars au 30 août 2026 — 88 Mo, 557 853 lignes. L'exposition est de six
    mois, pas de deux semaines
  - un **second canal non identifié** : uvicorn journalise lui aussi la ligne de
    requête complète, ~107 occurrences en 24 h dans un journal systemd de 3 Go
    sans rétention configurée
  - un **troisième canal**, relevé en review : `error_log`. Il écrit l'URI
    complète dans son contexte `request:` et `upstream:` sur tout événement de
    niveau `[error]` — un 502 suffit, et le redémarrage du service en ouvre
    précisément la fenêtre. Une occurrence déjà présente en production
- **Choix** : masquer plutôt que déplacer le secret. Le firmware HTG3/1.7.5 ne
  sait faire que des URL actions GET sans en-tête (décision 6), donc la clé reste
  dans l'URL ; ce qui change, c'est ce qu'on écrit sur disque
  - **nginx** : `location /api/releve/` dédiée, journalisée avec un `log_format`
    qui écrit `$uri` (chemin seul) au lieu de `$request` (URI complète). Le
    préfixe est plus long que `/api/`, donc prioritaire, et `/api/releves/`
    (lecture, au pluriel) ne correspond pas — elle garde sa journalisation
    complète, n'ayant pas de secret à cacher
  - **uvicorn** : `--no-access-log`. Ces lignes faisaient double emploi avec
    celles de nginx pour tout ce qui vient de l'extérieur. Ce n'est pas
    strictement « aucune information perdue » : `install.sh` et `update.sh`
    appellent `http://127.0.0.1:8042/api/sondes` en contournant nginx, et tout
    processus local pourrait en faire autant — ces requêtes-là ne laissent plus
    aucune trace. Elles ne portent pas de clé, et le compromis reste favorable,
    mais il n'est pas gratuit
  - **`error_log` du webhook relevé à `crit`** : les lignes `[error]` qui
    portaient l'URI disparaissent pour cette location. On garde le fait — un 502
    apparaît dans `access.log`, chemin masqué — on perd le détail de la cause.
    La lecture au pluriel conserve le sien, n'ayant pas de secret à cacher
  - **Bloc port 80** : même format de journalisation. Une action Shelly
    configurée en `http://` se ferait rediriger, et la ligne de redirection
    porterait la clé. Mesuré : 2 requêtes sur 8 095 passent par là — le cas est
    rare mais réel
  - **`location ^~ /api/releve/`** et non `location /api/releve/` : sans le
    `^~`, une location regex ajoutée un jour (`location ~ ^/api/`) l'emporterait
    sur le préfixe et le masquage disparaîtrait sans un mot de `nginx -t`
- **Écarté — `access_log off` sur la location** : on perdrait la trace que le
  webhook a été appelé, utile pour diagnostiquer une sonde muette. Le chemin, le
  code de retour et l'horodatage suffisent, la valeur mesurée étant de toute
  façon en base
- **Ce que ça ne règle pas** : le site est derrière Cloudflare, qui journalise
  l'URL complète de son côté. Hors de portée d'un correctif nginx, et à savoir
  avant de considérer le sujet clos
- **Vérifié en bac à sable** avant déploiement, sur la configuration exacte :
  webhook journalisé en `GET /api/releve/salon` sans paramètres (401 sur clé
  bidon, donc le proxy fonctionne), lecture au pluriel toujours journalisée avec
  sa query string, clé de test absente du log, et **les six en-têtes de sécurité
  toujours présents sur la nouvelle location** — c'est le piège `add_header` de
  la décision 16, qu'un seul en-tête posé dans ce bloc aurait déclenché
- **Les logs déjà écrits contiennent la clé.** Le masquage ne vaut que pour
  l'avenir : tant que la clé n'est pas changée, elle reste lisible dans
  `/var/log/nginx/access.log*` et dans le journal systemd

#### Rotation de la clé d'API

Procédure, à faire dans cet ordre — le service refuse toute écriture entre les
étapes 2 et 4, les sondes n'ayant pas encore la nouvelle clé :

0. Vérifier qu'un `/home/debian/meteo/.env` orphelin traîne encore (mode 644,
   clé différente de celle réellement utilisée) et le supprimer — il n'est lu par
   personne et ne sert qu'à égarer
1. Générer une clé : `openssl rand -hex 32`. **L'hexadécimal est délibéré** : la
   clé transite en query string, et un `base64` produirait des `+`, `/`, `=` —
   un `+` non encodé se décode en espace côté serveur, donc une authentification
   qui casse par intermittence, très pénible à diagnostiquer
2. La reporter dans `API_KEY=` de **`/home/debian/meteo/backend/.env`** — c'est
   celui que désignent `EnvironmentFile=` et le `load_dotenv()` lancé depuis
   `WorkingDirectory=/home/debian/meteo/backend`. Se tromper de fichier fait
   échouer toutes les écritures en 401 après l'étape 4, sans message explicite
3. `sudo systemctl restart maison-temp`
4. Reconfigurer **les deux URL actions de chaque boîtier Shelly** (« Changement
   de température » et « Changement d'humidité », cf. décision 6) avec la
   nouvelle valeur du paramètre `key`
5. Vérifier qu'un relevé arrive : `sqlite3` sur la base, ou attendre que le
   dashboard montre une mesure fraîche
6. Purger les traces de l'ancienne clé :
   `sudo truncate -s 0 /var/log/nginx/access.log` **et
   `sudo truncate -s 0 /var/log/nginx/error.log`** (ce second fichier en contient
   aussi), puis `sudo journalctl --rotate && sudo journalctl --vacuum-time=1s`.
   Il n'y a pas d'archives `access.log.*` à supprimer, logrotate ne tournant pas
   sur cette machine. Le `--vacuum-time` purge **tout** le journal systemd, pas
   seulement ce service : 3 Go d'historique de diagnostic pour toutes les
   applications de la machine. À mettre en balance avec le fait qu'après
   l'étape 4, l'ancienne clé ne vaut plus rien
7. Si l'étape 5 ne voit arriver aucun relevé, chercher les 401 dans
   `/var/log/nginx/access.log` — le canal `journalctl -u maison-temp`, réflexe
   habituel, ne les montre plus depuis `--no-access-log`

### Décision 18 (2026-08-30)

- **Contexte** : `/api/releves/{slug}?from=&to=` n'imposait aucune borne à
  l'écart entre les deux dates. `?from=1970-01-01&to=2100-01-01` faisait lire
  toutes les lignes de la sonde et les agréger en mémoire, sur une route **non
  authentifiée**, pour un résultat que personne ne regarde (issue #37)
- **Choix** : plafond à `MAX_RANGE_HOURS = PERIOD_HOURS["1an"]`, 400 au-delà. Le
  plafond vaut la plus longue période prédéfinie : il ne retire rien
  d'atteignable par l'interface, et le message dit **ce qui a été demandé et ce
  qui est admis**, sans quoi l'appelant ne sait pas de combien resserrer
- **Le plafond vaut 365 jours, pas « un an »** : une année bissextile ou une
  année calendaire à cheval sur un changement d'heure dépasse la borne de 24 h ou
  d'1 h. Front et back sont d'accord — ce n'est pas une divergence — mais la
  formulation « un an » est trompeuse et l'utilisateur qui saisit la même date un
  an plus tard peut être refusé une année sur quatre
- **Borne inclusive** : 365 jours pile passent, des deux côtés. Le serveur rejette
  sur `>` et le garde-fou client aussi — une divergence produirait soit un blocage
  sur une plage que l'API accepte, soit le bandeau d'échec opaque qu'on cherche
  justement à éviter. Deux tests l'épinglent de chaque côté, **et par le haut**
  (une seconde au-dessus doit être refusée) : sans ce second test, un plafond
  relâché d'une heure passait inaperçu
- **Message d'erreur arrondi par excès** (`math.ceil`) : avec un arrondi, tout
  dépassement entre 365 j et 365 j + 12 h affichait « 365 jours demandés, maximum
  365 jours » — un message qui se contredit précisément dans la zone la plus
  probable
- **Garde-fou client en plus du serveur**, et non à la place : sans lui, une
  sélection de dates trop large tombait dans le chemin d'échec générique de #36
  et affichait « certaines données n'ont pas pu être chargées ». C'est faux et
  inactionnable — le problème est la sélection de l'utilisateur, la seule chose
  qu'il puisse corriger. Le message dédié le dit
- **jsdom et `@testing-library/react` introduits** : la décision 14 avait pu se
  passer d'un DOM parce qu'elle testait de la géométrie pure. Ici le défaut
  n'était pas dans la fonction pure mais dans son **câblage** — le graphique
  restait dessiné avec les relevés de la plage précédente, sous un bandeau
  annonçant qu'aucune donnée n'avait été chargée. Aucun test de fonction pure ne
  pouvait l'attraper ; retirer le garde-fou du hook ou masquer le bandeau ne
  faisait échouer aucune vérification. Le hook et la vue sont désormais rendus
  pour de vrai
- **Résultat dérivé plutôt que remis à zéro dans l'effet** : y appeler `setState`
  provoque un rendu en cascade, et le linter le refuse. `useAnalyseReleves` rend
  donc une constante de module figée quand la plage dépasse le plafond
- **Duplication assumée de la constante** entre `backend/main.py` et
  `frontend/src/utils/analyseUtils.js`. Il n'y a pas de schéma partagé entre les
  deux côtés dans ce projet, et l'introduire pour une constante serait
  disproportionné. Un test frontend épingle la valeur (`MAX_RANGE_HOURS === 8760`)
  pour qu'une dérive tombe au lieu de passer inaperçue
- **Ce que le plafond ne fait pas** : la requête reste indexée
  (`idx_releves_sonde_date`), donc même sans plafond il n'y avait pas de scan de
  table complet — l'issue était imprécise sur ce point. Le coût réel est la
  lecture et l'agrégation des lignes de la plage, aujourd'hui modeste (8 090
  relevés sur trois mois) et croissant avec l'historique
- **Routes de lecture publiques, actées dans SPEC §6** : c'est la seconde moitié
  de l'issue. Elles le sont par conception, pas par omission — le front les
  appelle sans clé et le dashboard est en accès libre. Les protéger suppose
  l'authentification prévue en v2

### Décision 19 (2026-08-30)

- **Contexte** : `secrets.compare_digest` refuse les chaînes non-ASCII et lève
  une `TypeError`. Les deux points de contrôle de la clé lui passaient la valeur
  reçue telle quelle : une clé accentuée donnait un **500 au lieu d'un 401**, sur
  un chemin d'authentification et sans être authentifié (issue #44)
- **Choix** : comparer les encodages UTF-8 plutôt que les chaînes. La propriété
  de temps constant est conservée — c'est même la forme naturelle de
  `compare_digest`, qui travaille sur des octets — et une clé non-ASCII est
  traitée pour ce qu'elle est : une clé invalide
- **Les deux contrôles sont factorisés** dans `_key_is_valid`. Ils étaient
  dupliqués à l'identique, et le défaut existait donc en deux exemplaires : le
  webhook GET (clé en query string) et `require_api_key` (clé en en-tête)
- **Le chemin par en-tête est atteignable malgré les apparences** : un en-tête
  HTTP ne transporte pas d'UTF-8, et un client refuse même de l'émettre — mais il
  transporte des octets, que Starlette décode en latin-1. La valeur qui arrive
  contient alors bien du non-ASCII. Le test l'exerce avec des octets bruts
- **Pas de garde contre un encodage impossible, pour les deux appelants
  actuels** : une séquence d'octets invalide dans une URL est remplacée par
  U+FFFD au décodage, et un en-tête est décodé en latin-1 — ni l'un ni l'autre ne
  produit de demi-codet isolé. Vérifié sur `%ED%A0%80` et `%FF%FE`, qui donnent
  401. Un `try/except UnicodeEncodeError` avait été écrit puis retiré : il
  n'était atteignable par aucun de ces deux chemins. **Ce n'est pas une propriété
  de la fonction** : un corps JSON peut, lui, porter un demi-codet isolé — la
  review l'a montré, c'est l'issue #62, et le correctif y est ailleurs
- **Ordre des arguments load-bearing** : `compare_digest` boucle sur la longueur
  du **second**. L'entrée de l'appelant est donc passée en premier et le secret
  en second, pour que le nombre d'itérations ne dépende que du secret. Consigné
  dans la docstring, aucun test ne pouvant l'attraper
- **Le contrôle sur `API_KEY` vide est conservé et désormais testé** : sans lui,
  une installation dont la clé n'a pas été renseignée accepterait une clé vide,
  `compare_digest("", "")` étant vrai

---

### Décision 20 (2026-08-30)

- **Contexte** : `scripts/update.sh` se termine par `sudo systemctl restart
  maison-temp` puis deux contrôles de santé. Lancé hors terminal interactif,
  `sudo` ne peut pas demander de mot de passe ; sous `set -e`, le déploiement
  s'arrête là. Le service n'est pas redémarré — sans conséquence tant que la
  livraison ne touche que le frontend, bloquant dès qu'elle touche `backend/` —
  et surtout **le verdict de fin ne s'affiche jamais**, alors que tout le reste
  s'est bien passé (issue #48)
- **Choix** : une règle `NOPASSWD` dans `/etc/sudoers.d/maison-temp`, limitée à
  cette seule commande. Ni `restart *`, ni `systemctl` en général
- **La concession est plus étroite qu'il n'y paraît** : `debian` a déjà
  `(ALL : ALL) ALL` et peut donc redémarrer n'importe quel service en tapant son
  mot de passe. La règle n'ajoute aucun droit, elle retire l'exigence de mot de
  passe sur une commande. Ce qu'elle change réellement : un processus tournant
  sous `debian` pourrait redémarrer `maison-temp` sans s'authentifier, soit une
  coupure de quelques secondes du dashboard. C'est le pire cas, et il est
  accepté pour ce service
- **Le chemin doit être celui que `sudo` résoudra, pas celui que l'utilisateur
  résout** : `sudo` cherche la commande dans son `secure_path`
  (`/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`), le shell de
  `debian` dans un `PATH` qui commence par `~/.local/bin` et `~/bin` — deux
  répertoires qu'il peut écrire — et qui ne contient même pas `/usr/sbin`. Un
  `command -v systemctl` y trouverait un homonyme et poserait soit une règle qui
  ne s'applique jamais, soit un `NOPASSWD` sur un binaire réinscriptible par
  `debian`, c'est-à-dire root sans mot de passe. `install.sh` parcourt donc les
  répertoires système dans l'ordre de `secure_path`, et vérifie que le binaire
  trouvé appartient à root sans être modifiable par d'autres. **Ce n'est pas la
  justification qui figurait d'abord ici** : « une règle sur `systemctl` sans
  chemin serait contournable via le `PATH` » est fausse — `visudo` refuse une
  commande non qualifiée (`expected a fully-qualified path name`), le cas
  n'existe pas. La review a relevé la fausse prémisse et le vrai défaut qu'elle
  masquait
- **Le fichier est validé avant d'être posé, et posé atomiquement** : `visudo
  -cf` sur une copie temporaire, puis `install` sous un nom que `sudo` ignore (il
  saute les fichiers dont le nom contient un point) et `mv` en place. Une erreur
  de syntaxe dans `/etc/sudoers.d` verrouille `sudo` sur la machine, y compris
  pour la réparer — et `install` écrivant dans le fichier de destination, une
  interruption au mauvais moment y laisserait une ligne tronquée, soit exactement
  la panne que le contrôle cherche à éviter
- **Le contrôle final exécute la commande, il ne se contente pas de la
  consulter** : `sudo -l <commande>` répond « autorisée ? », pas « autorisée sans
  mot de passe ? ». `debian` ayant déjà `(ALL : ALL) ALL`, il répond oui à tout —
  mesuré : `sudo -n -l systemctl restart nginx` sort en 0. Le contrôle initial ne
  pouvait donc pas échouer, y compris si le fichier n'avait pas été posé. Il est
  remplacé par `sudo -k` puis `sudo -n … restart maison-temp` : le `-k` est
  indispensable, sans lui le cache d'authentification des étapes précédentes
  ferait passer le test quelle que soit la règle. Vérifié après `sudo -k` :
  `restart nginx`, `stop maison-temp` et `is-active maison-temp` sortent tous
  les trois en 1. Le contrôle est rendu avec les autres smoke tests, en `✓`/`✗`,
  sans faire échouer une installation par ailleurs réussie — c'est la leçon de
  cette issue même
- **Le motif est déjà en place sur ce serveur** pour d'autres projets
  (`fail2ban-client status`, `smartctl`, `needrestart -b`) : c'est une
  convention existante, pas une exception créée ici

---

### Décision 21 (2026-08-30)

- **Contexte** : `/api/sondes` calculait le plus récent des deux horodatages
  (température, humidité) puis le jetait — la construction du modèle recalculait
  `recu_le_temp or recu_le_hum`, qui renvoie toujours celui de la température dès
  qu'il existe, si vieux soit-il (issue #43)
- **Ce que `recu_le` veut dire est maintenant fixé** : le dernier signe de vie de
  la sonde, quelle que soit la grandeur qui l'a donné. C'est la question à
  laquelle le badge « Hors ligne » répond, et les deux grandeurs arrivent en
  relevés séparés — le Shelly les envoie en deux actions distinctes, l'une peut
  cesser de remonter sans l'autre
- **La comparaison porte sur les `datetime`, pas sur les chaînes ISO** : les
  8 114 lignes en base ont aujourd'hui toutes le même format, donc l'ordre
  lexicographique coïncide avec l'ordre chronologique — mais rien ne le garantit,
  et `_parse_recu_le` ramène par exemple un horodatage naïf à UTC, ce qu'une
  comparaison de chaînes ignorerait. **La sélection de la dernière ligne par
  grandeur reste lexicographique**, elle, puisqu'elle est faite par un `ORDER BY
  recu_le DESC` en SQL : c'est le même sujet côté base, et c'est l'issue #59. La
  review de #64 a relevé que cette justification n'était couverte par aucun test
  — deux ont été ajoutés, l'un sur des décalages horaires contradictoires, l'autre
  sur un horodatage sans fuseau (sans la normalisation, comparer naïf et tz-aware
  lève et l'endpoint répond 500)
- **Le marqueur ne tenait pas la card à 375 px**, largeur de référence du projet :
  passé d'un contexte 12 px à 28 px, « il y a 59 min » se coupait et l'orpheline
  héritait d'une line-box de 28 px ; en pleine largeur, la rangée éclatait mot par
  mot. Relevé en review, avec cette circonstance aggravante que les deux sondes
  actives sont seules dans leur section, donc rendues en pleine largeur — 100 %
  des cards étaient dans la disposition la plus dégradée. Corrigé par
  `white-space: nowrap` sur le marqueur, `.sonde-temp` en flex (le marqueur qui
  passe dessous emporte alors sa propre hauteur) et `flex-wrap` sur `.sonde-full`,
  qui dégrade en lignes entières au lieu de mots isolés
- **Garde sur une température absente** : `dernier_releve` existe dès qu'une des
  deux grandeurs est présente, donc `temperature` peut être `null` — et
  `toFixed` faisait alors disparaître tout le dashboard, faute d'error boundary.
  Défaut préexistant, mais que les tests ajoutés ici documentaient comme une
  réponse attendue sans le couvrir côté rendu
- **`recu_le_temp` est ajouté à la réponse** : `recu_le` étant désormais un
  maximum, il ne dit plus de quand date chaque grandeur. Sans cette information,
  la card ne peut plus signaler celle des deux qui traîne
- **Le correctif backend seul aurait dégradé l'affichage.** Avant, une sonde dont
  seule l'humidité remontait portait un badge « Hors ligne » — indu, mais qui
  signalait quelque chose. Après, elle est correctement vue en ligne : sans
  marqueur, sa température figée depuis des mois s'afficherait sur une card
  d'apparence saine. Le marqueur d'âge qui n'existait que pour l'humidité vaut
  donc pour les deux grandeurs, avec le même seuil de 30 min
- **Le seuil de 30 min est conservé tel quel** : deux relevés séparés de quelques
  minutes sont le cas nominal, le Shelly envoyant ses deux actions l'une après
  l'autre


### Décision 22 (2026-08-30)

- **Contexte** : `/api/releves/{slug}?from=&to=` construisait ses bornes par
  `start.isoformat()` / `end.isoformat()`, qui conservent le décalage horaire de
  l'écriture reçue, puis SQLite les comparait comme du texte à une colonne
  stockée en `+00:00`. Une plage écrite `12:00+02:00 → 14:00+02:00` ne lisait pas
  les instants qu'elle désigne mais la fenêtre telle qu'elle s'écrit, décalée de
  deux heures (issue #59). Mesuré en production : 2 points contre 6 pour les
  mêmes deux heures
- **Pourquoi le décalage ne compte pour rien** : il s'écrit après les chiffres
  comparés. À position égale, `+` et `-` s'ordonnent tous deux avant le `.` des
  microsecondes, donc face aux lignes en base la comparaison n'atteint jamais le
  suffixe — ce n'est pas un ordre approximatif. **C'est une propriété des données,
  pas du format** : `isoformat()` omet la fraction quand la microseconde est
  nulle, et une telle ligne porterait un `+` en position 19 elle aussi. Il n'y en
  a aucune sur les 8 138 lignes de production, mais rien ne l'interdit — l'ordre
  y reste chronologique (`+` avant `.` place la seconde pile avant les
  fractionnaires de la même seconde), et un test couvre le cas. La formulation
  initiale présentait cette propriété comme structurelle, la review l'a reprise
- **Correctif** : les bornes sont ramenées en UTC **dès le parsing**
  (`_parse_recu_le(from_).astimezone(timezone.utc)`), et non au moment de
  construire la requête. Tout ce qui suit — le contrôle `end <= start`, le
  plafond, la requête SQL — travaille alors sur les mêmes instants, et le
  traitement d'erreur reste au même endroit que celui du format invalide
- **Une date ISO valide peut ne pas être normalisable** : `0001-01-01T00:00:00+14:00`
  sort de `datetime.min` une fois ramenée en UTC, et `astimezone` lève une
  `OverflowError` que le `except ValueError` du parsing ne rattrape pas. La
  première version de ce correctif répondait donc 500 sur une lecture publique et
  non authentifiée, là où le code d'avant rendait 200 et une liste vide — une
  régression introduite par le correctif lui-même, relevée en review. Garde
  explicite et 400, avec un message distinct de celui du format : ces dates sont
  de l'ISO 8601 valide, l'appelant n'a rien mal écrit. Les mêmes années **sans**
  décalage restent acceptées, `astimezone` sur de l'UTC ne calculant rien — un
  témoin le tient, sans quoi rejeter toutes les dates extrêmes passerait pour un
  correctif
- **Le format `+00:00` est un invariant, pas un détail de mise en forme.**
  `isoformat()` sur un datetime UTC rend `+00:00` et non `Z` : c'est ce qui garde
  les bornes comparables aux lignes déjà en base. Un `Z` s'ordonnerait *après* le
  `.` des microsecondes et exclurait la seconde de la borne basse tout en incluant
  celle de la borne haute — le piège principal de ce correctif, tenu par un test
  dédié dont les deux lignes tombent sur la seconde exacte des bornes
- **Ce que le correctif ne touche pas** : le `ORDER BY recu_le DESC LIMIT 1` de
  `/api/sondes`, que la décision 21 renvoyait à cette issue, reste lexicographique.
  Il est correct tant que toute ligne s'écrit en UTC `+00:00`, ce que `_now_iso`
  garantit pour les deux chemins d'écriture — mais cet invariant n'était gardé par
  rien. Il l'est désormais par un test qui exerce le webhook GET et le POST et
  vérifie le format écrit — **sous heure locale décalée**, sans quoi il ne valait
  que la moitié de ce qu'il annonçait : la machine tournant en UTC, une écriture
  en heure locale *étiquetée* (`datetime.now().astimezone()`) y produit un
  `+00:00` correct et passait. Seule la variante naïve était attrapée. Relevé en
  review, et c'est exactement la correction déjà faite sur le test voisin des
  bornes naïves — le raisonnement n'avait pas été appliqué à celui-ci. Le passer en SQL sur des instants demanderait de
  changer le stockage, ce qui n'est pas justifié par un défaut qui n'existe pas
- **Le plafond de #37 valide maintenant la fenêtre réellement lue.** Il raisonne
  sur des instants (`end - start`) ; la requête comparait des chaînes. Une plage
  validée à 365 jours pouvait en lire une autre, jusqu'à 26 h d'écart entre les
  décalages extrêmes (`-12:00` et `+14:00`)
- **Les bornes naïves restent lues comme de l'UTC**, et le correctif en dépend :
  `astimezone` sur un datetime resté naïf supposerait l'heure locale du processus.
  C'est `_parse_recu_le` qui étiquette en amont. La machine tournant en UTC, un
  test qui se contenterait de passer une borne sans fuseau passerait quoi qu'on
  écrive : celui-ci force l'heure locale du processus à +14:00 le temps du test
- **L'interface n'était pas affectée** : `toIso()` dans `AnalyseView` n'émet que
  du `Z`. Vérifié sur une copie de la base de production, toutes les requêtes que
  l'interface émet réellement — six périodes prédéfinies et deux plages libres en
  `Z`, sur les trois sondes — rendent des réponses identiques avant et après. Seules
  les écritures avec décalage changent, ce qui est l'objet du correctif

---

## 7. Décisions abandonnées (historique)

*(vide pour l'instant)*

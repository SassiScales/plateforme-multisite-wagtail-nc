# Plateforme multi-site Wagtail et module « tableaux de données »

Démonstration technique réalisée par Sassi Scales LLC en septembre 2026, à l'appui de la
consultation 2026-DINUM-52051 du gouvernement de la Nouvelle-Calédonie. Elle fonctionne sur des
**données ouvertes réelles de data.gouv.nc**, lues en direct.

## Ce que la démonstration prouve

| Besoin du cahier des charges | Où le voir |
|---|---|
| Multi-site dans un seul back-office (UC003) | `gouv.localhost` et `drhfpnc.localhost` servis par la même instance |
| Droits hérités dans l'arborescence (UC001, UC006) | groupes « Pôle communication » (tout) et « Éditeurs DRH » (drhfpnc seulement) |
| Circuit de validation, brouillon, historique (UC004, UC019, UC020) | natifs Wagtail ; circuit « Validation par un administrateur » actif sur toutes les pages |
| Recherche du site dans les pages ET les lignes des tableaux (UC018, UC022) | page `/search/`, limitée aux données du site courant |
| Filtre instantané des tableaux | pendant la frappe, sans rechargement ; formulaire classique sans JavaScript |
| Éditeur guidé par blocs, mise en forme limitée, 3 gabarits (UC011, UC014, UC015) | modèle `PageContenu` |
| Bandeau d'alerte non bloquant (UC008) | bloc « Bandeau d'alerte » |
| Tableaux de données depuis data.gouv.nc, API REST ou CSV, sans code (UC010) | application `tableaux` |
| Recherche plein texte dans les données des tableaux (UC022) | champ de recherche du tableau et moteur du site |
| Alerte e-mail filtrée sur les nouvelles lignes (UC024) | formulaire « M'alerter », commande `lire_sources` |
| Redirections 301 (§ 3.5.a) | `/fr/douane/tarif-douanier` redirige vers la nouvelle page |
| Données structurées schema.org (UC026) | JSON-LD `WebPage` + `Dataset` sur chaque page à tableau |

Jeux de données utilisés : chapitres du tarif douanier, prix des médicaments en vigueur (Sempex),
assimilation des diplômes étrangers dans la fonction publique.

## Direction artistique

L'accueil est une carte marine vivante de la Nouvelle-Calédonie, dessinée à partir des limites des 33
communes publiées sur data.gouv.nc ; les lignes autour des îles sont des courbes de distance à
la côte (3 à 40 km) calculées par `design/carte_nc.py` (NumPy, SciPy, scikit-image). Ce ne sont pas
des profondeurs mesurées. Palette relevée sur gouv.nc (bleu lagon, turquoise, orange soleil),
polices Advent Pro et Public Sans hébergées localement. L'emblème (nautile et pin colonnaire) est
une création originale ; le logo officiel du gouvernement n'est pas utilisé.

Animations (tracé des lignes, bandeau « en direct », exemples de recherche tapés, compteurs)
toutes coupées lorsque l'utilisateur demande à réduire les mouvements (RGAA 13.8), et bandeau
défilant avec bouton de pause.

## Données et cartes

- Sept jeux de data.gouv.nc lus en direct : tarif douanier, prix des médicaments (Sempex), diplômes
  étrangers, établissements de santé, bornes de recharge, établissements artisanaux, limites communales.
- **Cartes sans fournisseur tiers** : points (santé, bornes) et cartes par commune (artisanat) tracés
  sur les limites communales officielles, avec la même projection que l'accueil (`tableaux/carte.py`).
- **Repères calculés** à chaque lecture (jamais saisis) : nombre, valeurs distinctes, moyenne, écart
  en % entre deux champs (ex. prix des médicaments aux îles comparés à Nouméa), valeur la plus fréquente.
- **Filtres en un clic** et **tri** des colonnes, configurables sans code.
- **Minimisation (RGPD)** : chaque source ne conserve que les champs choisis ; les autres ne sont ni
  stockés ni indexés.

## Qualité vérifiée

- **Accessibilité** : axe-core (WCAG 2.1 A et AA) sans aucune violation sur l'accueil, les pages à
  tableau, la recherche et le site drhfpnc ; navigation clavier, lien d'évitement, contrastes AA.
- **Sécurité** : politique de sécurité du contenu native de Django 6 (`script-src 'self'` sur le site
  public), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`.
- **Aucun appel à un tiers** : polices locales, pas de Gravatar, pas de vérification de version en
  ligne ; seules les API de data.gouv.nc sont interrogées, côté serveur.

## Lancer la démonstration

```
python3 -m venv .venv && .venv/bin/pip install "wagtail>=7,<8" requests
.venv/bin/python manage.py migrate
.venv/bin/python manage.py amorcer_demo --mot-de-passe <choisi>
.venv/bin/python manage.py runserver 8000
```

Puis ouvrir http://gouv.localhost:8000/, http://drhfpnc.localhost:8000/ et l'administration
http://gouv.localhost:8000/admin/ (comptes `admin`, `pole-com`, `editeur-drh`).

## Le module `tableaux`

- **`SourceDonnees`** (fragment administrable) : type Opendatasoft, REST JSON ou CSV ; filtre ODSQL
  facultatif ; champ identifiant ; fréquence de lecture. En cas de panne de la source, **le cache
  précédent est conservé** et l'erreur est affichée dans l'administration.
- **`Ligne`** : cache des lignes, indexé par le moteur de recherche de Wagtail.
- **`TableauBlock`** : bloc StreamField ; le contributeur choisit la source, les colonnes de la
  liste et de la fiche détail, la recherche, le nombre de lignes et l'alerte e-mail.
- **`lire_sources`** : commande à planifier (cron ou Celery beat) ; relit les sources dues et
  envoie un seul e-mail par abonné et par lecture.

## Reprise de contenus Drupal (application `reprise`)

Chaîne rejouable jusqu'à la bascule, testée sur 60 pages publiques de dittt.gouv.nc (Drupal 10) :

```
# 1. inventaire public du site (robots.txt respecté) : voir audit/crawl.py dans le dossier de l'offre
# 2. extraction des pages vers un lot JSON Lines (type Drupal, titre, corps, dates, images, documents)
.venv/bin/python manage.py extraire_drupal --inventaire inv_dittt.gouv.nc.sqlite --hote dittt.gouv.nc \
    --sortie migration/lots/dittt.jsonl --max 60
# 3. import : décision (migrer, fusionner, à arbitrer, supprimer), pages en blocs du design system,
#    liens internes réécrits, redirections 301 sur l'ancien domaine conservé, robot de vérification
.venv/bin/python manage.py importer_lot migration/lots/dittt.jsonl --site gouv.localhost \
    --ancien-domaine dittt.localhost --rubrique "Transports et territoires" --rapport migration/rapports/dittt
```

Résultat sur l'échantillon : 60 pages reprises (59 migrées, 1 fusionnée), 7 signalées à arbitrer,
60 redirections 301 sur 60 vérifiées en une seule étape. Les contenus repris ne sont pas versés dans ce
dépôt (dossier `migration/` exclu) : ils appartiennent au gouvernement de la Nouvelle-Calédonie.

## Suivi des pages (application `suivi`)

Chaque page a un contributeur propriétaire. Un compteur interne note les vues par page et par jour,
sans cookie ni adresse IP, robots exclus. Le tableau de bord de chaque contributeur montre ses pages les
plus vues et les liens morts relevés dans ses pages.

```bash
.venv/bin/python manage.py verifier_liens          # UC023 : tous les liens des pages publiées, chaque semaine
.venv/bin/python manage.py envoyer_bilan_mensuel   # UC007 : un e-mail par contributeur (vues + liens à corriger)
```

## Instance en ligne (une seule adresse)

`plateforme/settings/enligne.py` + application `deploiement` : sur un hébergement à adresse unique, les
sites restent distingués par hôte interne, choisi par `/_site/gouv/` ou `/_site/drhfpnc/` ; les anciennes
adresses se rejouent par `/_ancien/dittt/<chemin>`. `manage.py durcir_demo` remplace les mots de passe de
démonstration et crée un compte « visiteur » qui ouvre tout le back-office sans rien enregistrer.

## Limites connues de la démonstration

Habillage provisoire (le design system du GNC le remplacera) ; base SQLite (PostgreSQL en cible) ;
e-mails affichés dans la console ; compteur de vues interne (Matomo auto-hébergé en cible) ; authentification locale (Agent Connect / Keycloak en cible).

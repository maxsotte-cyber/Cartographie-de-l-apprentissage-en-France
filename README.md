# Carte des CFA et de leurs formations en apprentissage

Une carte interactive de tous les lieux de formation en apprentissage de France (métropole et outre-mer), avec la liste des formations proposées dans chacun.

- **11 510 lieux de formation**, chacun placé à son adresse réelle grâce aux coordonnées du catalogue.
- **53 681 formations** rattachées à ces lieux, soit 2 838 diplômes différents.
- **Un seul fichier HTML**, sans serveur : il s'ouvre dans un navigateur ou se publie tel quel (GitHub Pages, CMS…).

Données : export du Catalogue des formations en apprentissage du 24/11/2026.

## Ce que permet la carte

| Fonction | Détail |
|---|---|
| **Domaine** | Les 14 grands domaines du Formacode (Agriculture, Transformation, Échange et gestion…), avec sous chacun ses champs (Agriculture, production végétale ; Pêche, aquaculture…). Le choix d'un domaine limite aussi la liste des thèmes proposés. |
| **Thème (Formacode)** | Un thème choisi dans la liste (« Viticulture »), ou un mot qui retrouve tous les thèmes qui le contiennent (« agri » : agriculture, agricole…). Les thèmes de chaque formation s'affichent aussi dans la fiche du lieu. |
| **Recherche de formation** | Par intitulé ou par code RNCP, avec suggestions pendant la saisie. Plusieurs mots se combinent : « bts assurance ». |
| **Niveau** | Du niveau 3 (CAP) au niveau 7 (Bac +5), plusieurs niveaux à la fois. |
| **Type de diplôme** | BTS, CAP, titre professionnel, bac pro, licence professionnelle, master… |
| **Rentrée** | Les formations ouvertes pour une rentrée donnée (2026, 2027…). |
| **Autour d'une ville** | Ville ou code postal, dans un rayon de 5 à 100 km. Les résultats sont triés du plus proche au plus loin. |
| **Région et département** | Le département se limite à la région choisie. |
| **Nom du CFA** | Recherche par nom, raison sociale, UAI ou SIRET. |
| **Qualiopi** | Pour n'afficher que les organismes certifiés qualité. |
| **Fiche du lieu** | Nom, adresse, organisme responsable, SIRET, UAI, numéro de déclaration d'activité, et la **liste complète des formations**, classées par niveau, avec le code RNCP, la durée, les rentrées et des liens vers Onisep et la fiche du catalogue. Les formations qui correspondent à la recherche en cours sont mises en avant. |
| **Recherche Google** | Un bouton lance une recherche Google sur le nom du CFA suivi de son département. |
| **Itinéraire** | Ouvre le lieu dans Google Maps. |
| **Export CSV** | Une ligne par formation et par lieu, pour les résultats affichés. Le fichier s'ouvre directement dans Excel. |

## Fichiers

| Fichier | Rôle |
|---|---|
| `carte_cfa.html` | La carte, prête à l'emploi (environ 5 Mo, données comprises). |
| `generer_carte.py` | Le script qui fabrique la carte à partir des deux exports du catalogue. |
| `themes_formacode.csv` | La table RNCP → thèmes Formacode (export du tableur « Thèmes »). Non incluse dans ce dépôt. |
| `formacode_v14.csv` | Les descripteurs du Formacode V14 avec leur champ, tirés des 65 PDF de Centre Inffo. Non incluse dans ce dépôt. |
| `README.md` | Ce document. |

## Mettre la carte à jour

Le script n'a besoin d'aucune bibliothèque à installer : Python 3.9 ou plus suffit.

1. Sur le [Catalogue des formations en apprentissage](https://catalogue-apprentissage.intercariforef.org), exportez la liste des **établissements** et la liste des **formations** au format CSV.
2. Pour les thèmes, exportez le tableur « Thèmes » en CSV (Fichier → Télécharger → Valeurs séparées par des virgules), ou gardez `themes_formacode.csv`.
3. Lancez :

```bash
python generer_carte.py \
  --etablissements etablissements_2026-11-24.csv \
  --formations formation_2026-11-24.csv \
  --themes themes_formacode.csv \
  --formacode formacode_v14.csv \
  --sortie carte_cfa.html
```

Sans `--themes`, la carte est produite sans les filtres par thème et par domaine. Sans `--formacode`, elle garde le filtre par thème mais pas celui par domaine.

La date affichée sur la carte est lue dans le nom du fichier des formations ; gardez donc le nom d'origine de l'export.

## Comment le script construit la carte

1. **Lecture tolérante des exports.** Les fichiers utilisent le point-virgule comme séparateur. Certaines raisons sociales contiennent un guillemet qui n'est pas échappé, ce qui fait échouer les lecteurs CSV classiques (et BigQuery). Le script lit chaque ligne champ par champ et garde ces guillemets comme de simples caractères.
2. **Un point par lieu de formation.** Le point est placé à partir de la colonne « Lieu : géolocalisation ». Un même organisme peut enseigner sur plusieurs sites : chaque site devient un point, avec le nom de l'organisme formateur. L'organisme responsable est indiqué quand il est différent.
3. **Une formation par diplôme et par lieu.** Quand une même formation apparaît plusieurs fois au même endroit (une ligne par année de rentrée), les lignes sont fusionnées et les rentrées regroupées.
4. **Libellés lisibles.** Les libellés RNCP arrivent sans accents. Le script réapprend les accents à partir des libellés Carif-Oref du même export (« Systemes » devient « Systèmes »), et traduit les codes de diplôme (« DipViGrM » devient « Diplôme visé (grade de master) »).
5. **Thèmes.** Chaque formation reçoit les thèmes Formacode de son code RNCP (jusqu'à 5). 97,5 % des formations en ont au moins un ; les autres sont surtout des BTS et titres professionnels absents du tableur.
6. **Domaines.** Chaque thème est retrouvé dans le Formacode V14 par son libellé. Les 3 premiers chiffres de son code donnent son champ (24176 → champ 241, Énergie), et chaque champ appartient à un grand domaine. 1 317 thèmes sur 1 328 sont rangés ; les 11 autres sont des logiciels (Autocad, Catia…), qui relèvent d'une liste annexe du Formacode et non d'un domaine.
7. **Données compactes.** Chaque intitulé de diplôme n'est stocké qu'une fois, et les lieux y renvoient par un numéro. C'est ce qui permet de tenir 53 000 formations dans un seul fichier de 5 Mo.

## Sources

| Source | Producteur | Utilisation |
|---|---|---|
| [Catalogue des formations en apprentissage](https://catalogue-apprentissage.intercariforef.org) : export des formations | Réseau des Carif-Oref | Lieux de formation, coordonnées GPS, formations, codes RNCP et CFD, niveaux, rentrées |
| Catalogue des formations en apprentissage : export des établissements | Réseau des Carif-Oref | Lien vers la fiche de chaque établissement, numéro de déclaration d'activité |
| Tableur « Thèmes » (RNCP → Formacode) | Relevé personnel des descripteurs Formacode des fiches RNCP | Filtre par thème |
| [Formacode® V14](https://www.data.gouv.fr/datasets/formacode-r-version-14-thesaurus-de-loffre-de-formation-et-de-certification) : les 65 PDF des champs sémantiques | Centre Inffo | Code et champ de chaque thème |
| [Onisep](https://www.onisep.fr) | Onisep | Liens vers la fiche de chaque formation |
| Fond de carte [CARTO Positron](https://carto.com/basemaps) | © OpenStreetMap, © CARTO | Fond de carte clair, avec la clé CARTO de la carte précédente |

La carte utilise [Leaflet](https://leafletjs.com) pour l'affichage.

## Données sur BigQuery

Les deux exports sont aussi rangés dans le jeu de données `Cartographie_alternance` du projet `my-project-le-wagon-511810` :

- `formation_2026_brut` : table externe qui lit le fichier des formations sur Google Drive, une ligne de texte par formation ;
- `formation_2026_table` : copie native de cette table, lisible sans accès à Google Drive (61 063 lignes + l'en-tête).

Les tables externes `Etablissement_2026` et `formation_2026` d'origine ont été déclarées avec la virgule comme séparateur. Les exports utilisent le point-virgule, donc leurs colonnes sont mal découpées. Le script lit directement les fichiers CSV.

## Limites

- **Rentrées** : la colonne « Offre : Tags » indique les années pour lesquelles l'offre est publiée. Elle ne garantit pas l'ouverture effective d'une session.
- **Noms des communes** : ils sont écrits sans accents dans le catalogue (« Amberieu-en-Bugey »).
- **Fond de carte** : depuis août 2026, CARTO exige une clé, sinon les tuiles portent le filigrane « API KEY REQUIRED ». La clé est dans la variable `CARTO_CLE` du script ; elle est gratuite jusqu'à 5 millions de tuiles par mois et reste visible dans le HTML publié, ce qui est normal pour une clé de fond de carte. Les noms de lieux n'apparaissent qu'à partir du zoom 8, parce que CARTO les affiche en anglais aux petits zooms.
- **Grands domaines** : les PDF du Formacode V14 donnent les champs, pas leur regroupement en 14 grands domaines. Le script reprend le regroupement publié par Centre Inffo pour la V12 (63 champs). Les deux champs créés depuis sont rangés avec leurs voisins : « Gestion de la qualité » (314) dans Fonction production, « Encadrement, management » (321) dans Échange et gestion.
- **Formations sans thème** : 2,5 % des formations n'ont pas de thème, parce que leur code RNCP n'est pas dans le tableur. L'[export des fiches RNCP de France compétences](https://www.data.gouv.fr/datasets/repertoire-national-des-certifications-professionnelles-et-repertoire-specifique) donne les codes Formacode de toutes les fiches actives et comblerait ce manque ; sa version XML (478 Mo) est trop lourde pour être lue depuis Google Drive par le connecteur utilisé ici.

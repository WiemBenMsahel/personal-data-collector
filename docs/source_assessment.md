# Évaluation des sources de données

Projet : AlzheimerDataHub, module Architectures BD et collecte de données (ESEO 2026-2027)
Auteure : Wiem Ben M'sahel
Dates : évaluation initiale 03/11/2026, mise à jour 07/11/2026 (ajout de PubMed)

## 1. Comparaison des sources

| Critère | Source A : patients (retenue) | Source B : littérature PubMed (retenue, seconde source) | Source C : OASIS (candidate, non retenue) |
|---|---|---|---|
| Producteur et URL | Rabie El Kharoua, Kaggle : https://www.kaggle.com/datasets/rabieelkharoua/alzheimers-disease-dataset | NCBI, National Library of Medicine : API E-utilities, https://www.ncbi.nlm.nih.gov/books/NBK25497/ | OASIS, Washington University : https://sites.wustl.edu/oasisbrains/ |
| Mode d'accès | Téléchargement manuel depuis Kaggle (compte gratuit) | API HTTP publique (`esearch`, `efetch`), sans clé, adresse e-mail déclarée dans la requête | Inscription et acceptation d'un accord d'utilisation, accès sur demande |
| Format | CSV | XML (retourné par `efetch`) | NIfTI / JPEG + métadonnées CSV |
| Volume | 2149 lignes, 35 colonnes (592 Ko) | 195 articles distincts (50 par indicateur, 4 indicateurs) | Plusieurs Go d'images |
| Fréquence de mise à jour | Jamais (« Expected update frequency : Never » sur Kaggle) | Continue (nouveaux articles en permanence) | Ponctuelle |
| Clé ou identifiant | `PatientID` | `pmid` | Identifiant de sujet |
| Licence ou conditions | **Attribution 4.0 International (CC BY 4.0)** : https://creativecommons.org/licenses/by/4.0/ | Politique d'usage des données NCBI : https://www.ncbi.nlm.nih.gov/home/about/policies/ ; seules les métadonnées sont conservées, pas le texte des résumés | Data Use Agreement à accepter |
| Limite technique | Aucune (un seul fichier) | Débit limité (le script espace les requêtes, environ 3 par seconde au maximum) ; réponses XML à structure variable | Accès non immédiat, gros volumes, formats d'imagerie |
| Risque technique | Faible | Moyen (service externe, schéma variable) | Élevé |
| Données personnelles | Aucune : jeu étiqueté « Synthetic » sur Kaggle ; `DoctorInCharge` (valeur masquée `XXXConfid`) exclue du curated | Aucune : métadonnées d'articles publiés (pas de donnée de patient) | Anonymisées à la source |
| Date d'accès | 03/11/2026 | 06/11/2026 | Non utilisée |

## 2. Critères de sélection

| Critère | Source A | Source B |
|---|---|---|
| Répond directement à la question ? | Oui : MMSE, tension, cholestérol, âge et diagnostic | Indirectement : situe les quatre indicateurs dans la littérature |
| Accès stable, documenté, autorisé ? | Oui : page Kaggle publique, licence CC BY 4.0 | Oui : API publique documentée par le NCBI |
| Volume compatible avec le projet ? | Oui : traitement en moins d'une seconde | Oui : 195 articles, une dizaine de secondes |
| Champs à signification claire ? | Oui : description fournie par l'auteur du jeu | Oui : champs PubMed standards (PMID, titre, revue, année, termes MeSH) |
| Reproductible par un tiers ? | Oui : même fichier, même commande | Oui sans MongoDB (JSONL local) ; la publication Atlas demande un compte et une URI |

## 3. Décision

- **Source A retenue** : accessible, documentée, de volume adapté, reproductible. C'est la source principale (patients, relationnel).
- **Source B retenue comme seconde source** : documents semi-structurés (nombre variable de termes MeSH), stockés dans MongoDB Atlas. Il n'y a **aucune clé commune** avec les patients : le recoupement se fait par indicateur, pas par patient.
- **Source C écartée** : accès sur demande, volumes d'images hors proportion avec le besoin ; conservée comme évolution possible.

## 4. Conformité et minimisation

- **Attribution (CC BY 4.0) :** jeu *Alzheimer's Disease Dataset* de Rabie El Kharoua, publié sur Kaggle sous licence CC BY 4.0. Les données ont été modifiées par ce projet (sélection de 11 colonnes sur 35, renommage, rejet des lignes invalides, variables calculées).
- **Minimisation :** seules les colonnes utiles à la question sont conservées dans le curated (11 sur 35 ; la colonne `Ethnicity`, par exemple, ne l'est pas). Le fichier des rejets garde en revanche la ligne source complète pour le diagnostic : acceptable pour un jeu synthétique, à filtrer sur des données réelles. Pour PubMed, seules les métadonnées sont stockées.
- Aucun secret, identifiant ou donnée personnelle de tiers dans le dépôt. L'URI MongoDB est dans `.env`, non versionné.
- Le jeu patients étant synthétique, les résultats de l'analyse ne constituent pas des conclusions médicales.

## 5. Limites

- Le dépôt ne contient que des échantillons des deux sources (`data/raw/sample_source.csv`, 150 lignes ; `data/raw/sample_pubmed.xml`, 5 articles). Le fichier Kaggle complet est à retélécharger.
- Un contrôle de cohérence révèle que 186 lignes (8,7 %) ont une tension diastolique supérieure à la systolique, ce qui est physiologiquement impossible. Elles sont rejetées et conservées dans `data/rejected/rejected_rows.csv`.
- PubMed : sélection de 50 articles récents par indicateur avec une requête simple, sans prétention de revue systématique.
# Évaluation des sources de données

Projet : AlzheimerDataHub, module Architectures BD et collecte de données (ESEO 2026-2027)
Auteure : Wiem Ben M'sahel
Date de l'évaluation : 03/11/2026

## 1. Comparaison des sources

| Critère | Source A (retenue) | Source B (candidate, non retenue) |
|---|---|---|
| Producteur et URL | Rabie El Kharoua, Kaggle : https://www.kaggle.com/datasets/rabieelkharoua/alzheimers-disease-dataset | OASIS, Washington University : https://sites.wustl.edu/oasisbrains/ |
| Mode d'accès | Téléchargement manuel depuis Kaggle (compte gratuit), documenté dans le README | Inscription et acceptation d'un accord d'utilisation, accès sur demande |
| Format | CSV (`alzheimers_disease_data.csv`) | NIfTI / JPEG + métadonnées CSV |
| Volume | 2149 lignes, 35 colonnes (592 Ko) | Plusieurs Go d'images |
| Fréquence de mise à jour | Jamais (« Expected update frequency : Never » sur Kaggle), jeu figé | Mises à jour ponctuelles |
| Clé ou identifiant | `PatientID` (clé métier, unique) | Identifiant de sujet |
| Licence ou conditions | **Attribution 4.0 International (CC BY 4.0)** : https://creativecommons.org/licenses/by/4.0/ (utilisation libre avec mention de l'auteur, de la source et de la licence) | Data Use Agreement à accepter |
| Risque technique | Faible : un seul fichier, schéma clair | Élevé : accès non immédiat, gros volumes, formats d'imagerie |
| Données personnelles | Aucune donnée nominative : jeu étiqueté « Synthetic » sur Kaggle. La colonne `DoctorInCharge` contient la valeur masquée `XXXConfid` et est exclue de la zone curated | Anonymisées à la source |

## 2. Critères de sélection appliqués à la source A

| Critère | Réponse |
|---|---|
| Répond directement à la question ? | Oui : contient MMSE, tension, cholestérol, âge et le diagnostic |
| Accès stable, documenté, autorisé ? | Oui : page Kaggle publique, licence CC BY 4.0, téléchargement légitime avec compte |
| Volume compatible avec le TP ? | Oui : 2149 lignes, traitement en moins d'une seconde |
| Champs à signification claire ? | Oui : dictionnaire de données fourni par l'auteur du jeu |
| Reproductible par un autre étudiant ? | Oui : même fichier, même commande (`python src/pipeline.py`) |

## 3. Décision

La **source A** est retenue : accessible, documentée, de volume adapté et reproductible.
La **source B** est conservée comme évolution possible (intégration d'images IRM dans un stockage objet), hors périmètre du TP.

## 4. Conformité et limites

- **Attribution (CC BY 4.0) :** jeu de données *Alzheimer's Disease Dataset* de Rabie El Kharoua, publié sur Kaggle sous licence CC BY 4.0. Les données ont été transformées par ce projet (sélection de colonnes, renommage, rejet des lignes invalides, variables calculées).
- Aucun secret, identifiant ou donnée personnelle de tiers dans le dépôt.
- Le jeu étant synthétique, les résultats de l'analyse ne constituent pas des conclusions médicales.
- Le dépôt ne contient qu'un échantillon de 150 lignes du fichier source (`data/raw/sample_source.csv`). Le fichier complet est à retélécharger depuis Kaggle.
- Un contrôle de cohérence a révélé que 186 lignes (8,7 %) ont une tension diastolique supérieure à la systolique, ce qui est physiologiquement impossible. Elles sont rejetées et conservées dans `data/rejected/rejected_rows.csv`.
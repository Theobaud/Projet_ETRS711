Appli web pour gérer une cave à vin : cave perso, étagères, lots/slots, consommation archivée, avis et KPIs.
Le code suit exactement 7 classes (diagramme) : Utilisateur, Cave, Etagere, Bouteille, Stock_bouteilles, Revue, SortieArchive.

Fonctionnalités

Authentification (inscription/connexion/déconnexion — mots de passe hashés).
Cave auto-créée avec Étagère 1 (10 places).
Gestion des étagères.
Bouteilles : création (photo optionnelle) + catalogue léger.
Stock par lots avec slots → calcul du prochain slot libre.
Consommation : décrément + archivage (motif “BUE”), option “Boire & noter”.
Avis (0–20 + commentaire), moyenne par bouteille, page Avis de la communauté.
KPIs (header) : valeur totale, nb bouteilles/lots/bues, nb d’avis, top 4.


Installation
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # sinon voir bloc ci-dessous


requirements.txt minimal :

Flask
Werkzeug

Lancer l’application
python app.py
# Ouvrir http://127.0.0.1:5000


Au premier lancement, ensure_schema() applique des migrations douces (ajouts de colonnes si manquantes).

Structure
.
├─ app.py              # routes Flask + logique d’orchestration
├─ models.py           # accès DB + 7 dataclasses (pattern Active Record léger)
├─ templates/          # Jinja2 (index, ma_cave, bouteille_detail, avis, etc.)
├─ static/
│  ├─ style.css
│  └─ uploads/         # photos bouteilles (créé automatiquement)
└─ cave.db             # SQLite (généré à l’exécution)


Sécurité & robustesse

Mots de passe hashés (Werkzeug).
Uploads filtrés (extensions/poids).
Contrôle d’appartenance : actions limitées à la cave de l’utilisateur.
Protection des liens en vue triée : si id_bouteille est NULL (slots vides issus du LEFT JOIN), pas de lien vers la fiche (évitant un BuildError).

#BAUDOIN Théo - PROJET M1 

from __future__ import annotations

import os
import io
import csv
from datetime import datetime
from functools import wraps
from typing import Optional

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import (
    Database as DB,
    ensure_schema,
    Utilisateur, Cave, Etagere, Stock_bouteilles,
    Bouteille, Revue, SortieArchive,
)

# ---------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = "dev"  # ⚠ à remplacer en prod

# Migrations "douces" (ajoute colonnes si absentes, idempotent)
ensure_schema()

# Uploads
UPLOAD_DIR = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 Mo
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------
# Petites aides
# ---------------------------------------------------------------------
def current_uid() -> Optional[int]:
    """Renvoie l'ID utilisateur en session (ou None)."""
    return session.get("uid")


def allowed_file(filename: str) -> bool:
    """Vérifie si l'extension du fichier est autorisée pour l'upload."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view):
    """Décorateur qui force l'authentification avant d'accéder à la vue."""
    @wraps(view)
    def wrapper(*a, **kw):
        if not current_uid():
            return redirect(url_for("connexion", next=request.path))
        return view(*a, **kw)
    return wrapper


# ---------------------------------------------------------------------
# Tableau de bord (KPIs)
# ---------------------------------------------------------------------
def build_user_stats(uid: Optional[int]) -> dict:
    """
    Construit les statistiques affichées dans l'en-tête (KPIs).
    - top_rated : 4 bouteilles les mieux notées (moyenne + nb d'avis)
    - Si uid:
        * my_bottles : nb total de bouteilles en cave
        * my_lots    : nb de lots distincts (>0)
        * my_value   : valeur estimée (quantité * prix)
        * my_drunk   : nb de bouteilles bues (archives motif 'BUE')
        * my_reviews : nb d'avis rédigés par l'utilisateur
    """
    stats = {
        "my_bottles": 0,
        "my_value": 0.0,
        "my_drunk": 0,
        "my_reviews": 0,
        "my_lots": 0,
        "top_rated": [],
    }

    with DB() as c:
        # Top 4 global (bouteilles ayant au moins 1 avis)
        stats["top_rated"] = c.execute("""
            SELECT b.id_bouteille, b.nom, b.domaine, b.annee, b.type, b.region,
                   ROUND(AVG(r.score), 2) AS moyenne, COUNT(r.id_revue) AS n
            FROM bouteille b
            JOIN revue r ON r.bouteille_id = b.id_bouteille
            GROUP BY b.id_bouteille
            HAVING n >= 1
            ORDER BY moyenne DESC, n DESC
            LIMIT 4
        """).fetchall()

        if not uid:
            return stats

        # KPIs liés à l'utilisateur courant
        row = c.execute("""
            SELECT
              COALESCE(SUM(s.quantite), 0) AS q_bottles,
              COALESCE(SUM(CASE WHEN s.quantite > 0 THEN 1 ELSE 0 END), 0) AS q_lots,
              COALESCE(SUM(s.quantite * b.prix), 0.0) AS v_value
            FROM cave cv
            JOIN etagere e              ON e.id_cave      = cv.id_cave
            LEFT JOIN stock_bouteilles s ON s.id_etagere   = e.id_etagere
            LEFT JOIN bouteille b        ON b.id_bouteille = s.id_bouteille
            WHERE cv.id_utilisateur = ?
        """, (uid,)).fetchone()

        stats["my_bottles"] = int(row["q_bottles"] or 0)
        stats["my_lots"] = int(row["q_lots"] or 0)
        stats["my_value"] = float(row["v_value"] or 0.0)

        row2 = c.execute("""
            SELECT COALESCE(SUM(a.quantite), 0) AS drunk
            FROM sortie_archive a
            JOIN stock_bouteilles s ON s.id_stock = a.id_stock
            JOIN etagere e          ON e.id_etagere = s.id_etagere
            JOIN cave cv            ON cv.id_cave   = e.id_cave
            WHERE a.id_utilisateur = ?
              AND cv.id_utilisateur = ?
              AND UPPER(a.motif)='BUE'
        """, (uid, uid)).fetchone()
        stats["my_drunk"] = int(row2["drunk"] or 0)

        row3 = c.execute("SELECT COUNT(*) AS n FROM revue WHERE auteur_id=?", (uid,)).fetchone()
        stats["my_reviews"] = int(row3["n"] or 0)

    return stats


@app.context_processor
def inject_stats():
    """
    Injecte `stats` dans tous les templates Jinja (header/KPIs).
    En cas d'erreur, renvoie des valeurs neutres (évite de casser l'affichage).
    """
    try:
        return dict(stats=build_user_stats(current_uid()))
    except Exception:
        return dict(stats={"my_bottles": 0, "my_reviews": 0, "my_value": 0,
                           "my_drunk": 0, "my_lots": 0, "top_rated": []})


# ---------------------------------------------------------------------
# Routes publiques
# ---------------------------------------------------------------------
@app.route("/")
def index():
    """Accueil (les KPIs/Top sont fournis par le context_processor)."""
    return render_template("index.html")


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    """
    Inscription : crée l'utilisateur, puis sa cave + une Étagère 1 (capacité 10).
    """
    if request.method == "POST":
        nom = request.form.get("nom")
        email = (request.form.get("email") or "").strip().lower()
        pwd = request.form.get("mot_de_passe")

        if not nom or not email or not pwd:
            flash("Tous les champs sont requis.", "error")
            return render_template("inscription.html")

        if Utilisateur.get_by_email(email):
            flash("Cet email est déjà utilisé.", "error")
            return render_template("inscription.html")

        # 1/ crée l'utilisateur
        new_uid = Utilisateur.create(nom, email, generate_password_hash(pwd))
        # 2/ crée sa cave + Étagère 1
        cave_id = Cave.create_for_user(new_uid, f"Cave de {nom}")
        Etagere.create(cave_id, "Étagère 1", 10)

        flash("Compte créé. Connecte-toi.", "success")
        return redirect(url_for("connexion"))

    return render_template("inscription.html")


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    """Connexion simple par email + mot de passe (hashé)."""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        mdp = request.form.get("mot_de_passe") or ""
        u = Utilisateur.get_by_email(email)
        if not u or not u.mot_de_passe or not check_password_hash(u.mot_de_passe, mdp):
            flash("Identifiants invalides.", "error")
            return render_template("connexion.html", email=email), 401
        session["uid"] = u.id_utilisateur
        flash(f"Heureux de te revoir, {u.nom} ", "success")
        return redirect(request.args.get("next") or url_for("index"))
    return render_template("connexion.html")


@app.route("/deconnexion")
def deconnexion():
    """Déconnecte l'utilisateur (nettoie la session)."""
    session.pop("uid", None)
    flash("Déconnecté.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------
# Bouteilles : fiche + avis
# ---------------------------------------------------------------------
@app.route("/bouteilles/<int:bid>", methods=["GET", "POST"])
def bouteille_detail(bid: int):
    """
    Affiche la fiche bouteille et ses avis.
    POST : ajoute un avis (score 0..20 optionnel + commentaire optionnel).
    """
    b = Bouteille.get(bid)
    if not b:
        flash("Bouteille introuvable.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        if not current_uid():
            flash("Connecte-toi pour publier un avis.", "error")
            return redirect(url_for("connexion", next=request.path))

        score_raw = (request.form.get("score") or "").strip()
        commentaire = (request.form.get("commentaire") or "").strip() or None
        score = None

        if score_raw != "":
            try:
                score = float(score_raw)
                if not (0 <= score <= 20):
                    raise ValueError()
            except ValueError:
                flash("La note doit être un nombre entre 0 et 20 (ou vide).", "error")
                return redirect(url_for("bouteille_detail", bid=bid))

        Revue.add(bid, current_uid(), score, commentaire)
        flash("Avis publié ✅", "success")
        return redirect(url_for("bouteille_detail", bid=bid))

    return render_template(
        "bouteille_detail.html",
        b=b,
        moyenne=Revue.avg_for_bottle(bid),
        revues=Revue.list_for_bottle(bid),
    )


# ---------------------------------------------------------------------
# Page “Avis de la communauté”
# ---------------------------------------------------------------------
@app.route("/avis")
def avis():
    """
    Liste les avis (tous utilisateurs) avec recherche ?q=... (nom/domaine/région).
    """
    q = (request.args.get("q") or "").strip()
    rows = Revue.community_reviews(q)
    return render_template("avis.html", q=q, rows=rows)


# ---------------------------------------------------------------------
# Ma cave (tri / filtre / opérations de stock)
# ---------------------------------------------------------------------
@app.route("/ma-cave")
@login_required
def ma_cave():
    """
    Vue 'Ma cave' :
    - crée automatiquement cave + Étagère 1 si l'utilisateur n'en a pas,
    - applique tri/filtre,
    - affiche les étagères et les slots (physiques ou tri logique).
    """
    uid = current_uid()

    # Garantit l'existence de la cave
    cave = Cave.get_by_user(uid)
    if not cave:
        user = Utilisateur.get(uid)
        cave_id = Cave.create_for_user(uid, f"Cave de {user.nom if user else 'Utilisateur'}")
        Etagere.create(cave_id, "Étagère 1", 10)
        cave = Cave.get_by_user(uid)
        flash("Ta cave a été créée automatiquement ✅", "success")

    # Paramètres de tri / filtre (GET)
    sort = (request.args.get("sort") or "slot").lower()
    direction = (request.args.get("dir") or "asc").lower()
    filt_field = (request.args.get("filter") or "").lower()   # 'region' | 'type' | 'annee' | 'domaine' | 'nom'
    filt_value = (request.args.get("value") or "").strip()

    etageres = Etagere.list_for_cave(cave.id_cave)
    stock_all = Stock_bouteilles.list_for_user(uid)

    # Options de filtre (valeurs distinctes existantes)
    def distinct(rows, key):
        return sorted({str(r[key]) for r in rows if r[key] is not None and str(r[key]).strip() != ""})

    filter_values_map = {
        "region":  distinct(stock_all, "region"),
        "type":    distinct(stock_all, "type"),
        "annee":   sorted({int(r["annee"]) for r in stock_all if r["annee"] is not None}),
        "domaine": distinct(stock_all, "domaine"),
        "nom":     distinct(stock_all, "nom"),
    }
    current_options = filter_values_map.get(filt_field, [])

    # Filtrage
    stock = stock_all
    if filt_field in filter_values_map and filt_value:
        if filt_field == "annee":
            try:
                v = int(filt_value)
                stock = [r for r in stock_all if r["annee"] == v]
            except ValueError:
                stock = stock_all
        else:
            lv = filt_value.lower()
            stock = [r for r in stock_all if (r[filt_field] or "").lower() == lv]

    # Tri (clé serveur)
    key_map = {
        "slot":    lambda r: (r["id_etagere"], r["slot"] if r["slot"] is not None else 9999),
        "nom":     lambda r: (r["id_etagere"], (r["nom"] or "").lower()),
        "domaine": lambda r: (r["id_etagere"], (r["domaine"] or "").lower()),
        "annee":   lambda r: (r["id_etagere"], r["annee"] or -9999),
        "type":    lambda r: (r["id_etagere"], (r["type"] or "").lower()),
        "region":  lambda r: (r["id_etagere"], (r["region"] or "").lower()),
    }
    key_fn = key_map.get(sort, key_map["slot"])
    stock = sorted(stock, key=key_fn, reverse=(direction == "desc"))

    bottles_all = Bouteille.list_all_light()

    return render_template(
        "ma_cave.html",
        cave=cave, etageres=etageres, stock=stock, bottles_all=bottles_all,
        sort=sort, direction=direction, filt_field=filt_field,
        filt_value=filt_value, current_options=current_options,
    )


@app.route("/bouteilles/nouvelle", methods=["GET", "POST"])
@login_required
def bouteille_nouvelle():
    """
    Ajout d'une nouvelle bouteille + placement immédiat (lot).
    - calcule un slot libre si le slot fourni est vide/invalide,
    - fusionne avec un lot existant si même (étagère, slot, bouteille).
    """
    uid = current_uid()
    cave = Cave.get_by_user(uid)
    if not cave:
        Cave.create_for_user(uid, f"Cave de {Utilisateur.get(uid).nom}")
        flash("Cave créée. Ajoute des étagères puis des bouteilles.", "info")
        return redirect(url_for("ma_cave"))

    shelves = Etagere.list_for_cave(cave.id_cave)

    if request.method == "POST":
        # Champs bouteille
        domaine = (request.form.get("domaine") or "").strip()
        nom     = (request.form.get("nom") or "").strip()
        type_   = (request.form.get("type") or "").strip()
        annee   = request.form.get("annee", type=int)
        region  = (request.form.get("region") or "").strip()
        prix    = request.form.get("prix", type=float)

        # Placement
        id_etagere = request.form.get("id_etagere", type=int)
        quantite   = request.form.get("quantite", type=int)
        slot       = request.form.get("slot", type=int) 

        # Validations basiques
        if not (domaine and nom and type_ and annee and region and prix is not None):
            flash("Tous les champs de la bouteille sont requis.", "error")
            return redirect(url_for("bouteille_nouvelle"))
        if not (id_etagere and quantite and quantite > 0):
            flash("Choisis une étagère et une quantité > 0.", "error")
            return redirect(url_for("bouteille_nouvelle"))
        if Etagere.capacity_left(id_etagere) < quantite:
            flash("Capacité insuffisante sur l’étagère.", "error")
            return redirect(url_for("bouteille_nouvelle"))

        # Choix du slot (auto si vide / hors bornes)
        shelf_map = {e.id_etagere: e for e in shelves}
        cap = shelf_map[id_etagere].capacite
        if not slot or slot < 1 or slot > cap:
            slot = Stock_bouteilles.next_free_slot(id_etagere, cap)

        # Upload photo (facultatif)
        photo_path = None
        file = request.files.get("photo")
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Format d'image non autorisé (png/jpg/jpeg/gif/webp).", "error")
                return redirect(url_for("bouteille_nouvelle"))
            filename = secure_filename(file.filename)
            base, ext = os.path.splitext(filename)
            unique = f"{base}_{uid}_{int(datetime.now().timestamp())}{ext}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique)
            file.save(save_path)
            photo_path = f"uploads/{unique}"

        # Création bouteille + ajout de lot
        with DB() as c:
            cur = c.execute("""
                INSERT INTO bouteille(domaine, nom, type, annee, region, prix, photo)
                VALUES (?,?,?,?,?,?,?)
            """, (domaine, nom, type_, annee, region, prix, photo_path))
            id_bouteille = cur.lastrowid

        Stock_bouteilles.add_or_increment(id_etagere, id_bouteille, quantite, slot)
        flash("Bouteille ajoutée à ta cave ✅", "success")
        return redirect(url_for("ma_cave"))

    return render_template("bouteille_nouvelle.html", shelves=shelves)


@app.route("/stock/consommer", methods=["POST"], endpoint="stock_consommer")
@login_required
def stock_consommer():
    """
    Consomme une quantité depuis un lot :
    - archive la sortie (motif 'BUE' + snapshot id_bouteille/id_etagere),
    - décrémente/supprime le lot,
    - option : redirige vers la fiche bouteille pour noter.
    """
    uid = current_uid()
    id_stock = request.form.get("id_stock", type=int)
    q = request.form.get("quantite", type=int)
    want_review = (request.form.get("redirect_to_review") == "1")

    if not id_stock or not q or q < 1:
        flash("Quantité invalide.", "error")
        return redirect(url_for("ma_cave"))

    lot = Stock_bouteilles.get_lot(id_stock)
    if not lot:
        flash("Lot introuvable.", "error")
        return redirect(url_for("ma_cave"))

    cave = Cave.get_by_user(uid)
    shelf_ids = {e.id_etagere for e in Etagere.list_for_cave(cave.id_cave)}
    if lot.id_etagere not in shelf_ids:
        flash("Accès refusé à ce lot.", "error")
        return redirect(url_for("ma_cave"))

    try:
        SortieArchive.add(
            id_stock=lot.id_stock,
            id_utilisateur=uid,
            quantite=q,
            motif="BUE",
            id_bouteille=lot.id_bouteille,
            id_etagere=lot.id_etagere,
        )
        Stock_bouteilles.decrement(id_stock, q)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("ma_cave"))

    if want_review:
        flash("Sortie enregistrée. Que penses-tu de cette bouteille ? 🍷", "success")
        return redirect(url_for("bouteille_detail", bid=lot.id_bouteille, review=1))

    flash("Santé ! 🍷 Sortie enregistrée.", "success")
    return redirect(url_for("ma_cave"))


@app.post("/stock/affecter")
@login_required
def stock_affecter():
    """
    Affecte (ou réaffecte) un slot à un lot **sans emplacement** ou mal placé.
    - si slot vide ou invalide : calcule le prochain slot libre.
    """
    uid = current_uid()
    id_stock = request.form.get("id_stock", type=int)
    slot = request.form.get("slot", type=int)

    lot = Stock_bouteilles.get_lot(id_stock)
    if not lot:
        flash("Lot introuvable.", "error")
        return redirect(url_for("ma_cave"))

    cave = Cave.get_by_user(uid)
    shelf_ids = {e.id_etagere for e in Etagere.list_for_cave(cave.id_cave)}
    if lot.id_etagere not in shelf_ids:
        flash("Accès refusé à ce lot.", "error")
        return redirect(url_for("ma_cave"))

    if not slot or slot < 1:
        E = [e for e in Etagere.list_for_cave(cave.id_cave) if e.id_etagere == lot.id_etagere][0]
        slot = Stock_bouteilles.next_free_slot(lot.id_etagere, E.capacite)

    Stock_bouteilles.set_slot(id_stock, slot)
    flash(f"Lot affecté au slot #{slot} ✅", "success")
    return redirect(url_for("ma_cave"))


@app.route("/stock/ajouter-catalogue", methods=["POST"])
@login_required
def stock_add_from_catalog():
    """
    Ajoute (ou incrémente) un lot à partir d'une bouteille existante du catalogue.
    - calcule un slot libre si slot non renseigné.
    """
    uid = current_uid()
    cave = Cave.get_by_user(uid)
    if not cave:
        flash("Cave introuvable.", "error")
        return redirect(url_for("ma_cave"))

    id_bouteille = request.form.get("id_bouteille", type=int)
    id_etagere   = request.form.get("id_etagere", type=int)
    quantite     = request.form.get("quantite", type=int)
    slot         = request.form.get("slot", type=int)
    if slot == 0:
        slot = None

    if not (id_bouteille and id_etagere and quantite and quantite > 0):
        flash("Champs invalides.", "error")
        return redirect(url_for("ma_cave"))

    shelves = {e.id_etagere: e for e in Etagere.list_for_cave(cave.id_cave)}
    E = shelves.get(id_etagere)
    if not E:
        flash("Étagère invalide.", "error")
        return redirect(url_for("ma_cave"))

    left = Etagere.capacity_left(id_etagere)
    if left < quantite:
        flash(f"Capacité insuffisante : {left} place(s) restante(s).", "error")
        return redirect(url_for("ma_cave"))

    if slot is None:
        slot = Stock_bouteilles.next_free_slot(id_etagere, E.capacite)

    Stock_bouteilles.add_or_increment(id_etagere, id_bouteille, quantite, slot)
    flash("Bouteille ajoutée à ta cave ✅", "success")
    return redirect(url_for("ma_cave"))


# ---------------------------------------------------------------------
# Gestion des étagères
# ---------------------------------------------------------------------
@app.post("/etageres/ajouter")
@login_required
def etagere_ajouter():
    """
    Ajoute une étagère à la cave de l'utilisateur.
    - nom vide => "Étagère N"
    - capacité bornée 1..200
    """
    uid = current_uid()
    cave = Cave.get_by_user(uid)
    if not cave:
        flash("Cave introuvable.", "error")
        return redirect(url_for("ma_cave"))

    nom = (request.form.get("nom") or "").strip()
    capacite = request.form.get("capacite", type=int)

    if not nom:
        nb_exist = len(Etagere.list_for_cave(cave.id_cave))
        nom = f"Étagère {nb_exist + 1}"

    if not capacite or capacite < 1 or capacite > 200:
        flash("Capacité invalide (1–200).", "error")
        return redirect(url_for("ma_cave", _anchor="add-shelf"))

    Etagere.create(cave.id_cave, nom, capacite)
    flash(f"Étagère « {nom} » ajoutée ({capacite} emplacements) ✅", "success")
    return redirect(url_for("ma_cave"))


@app.post("/etageres/supprimer")
@login_required
def etagere_supprimer():
    """
    Supprime une étagère **si et seulement si** elle est vide.
    """
    uid = current_uid()
    cave = Cave.get_by_user(uid)
    if not cave:
        flash("Cave introuvable.", "error")
        return redirect(url_for("ma_cave"))

    id_etagere = request.form.get("id_etagere", type=int)
    if not id_etagere:
        flash("Étagère invalide.", "error")
        return redirect(url_for("ma_cave"))

    ok = Etagere.delete_if_empty(id_etagere, cave.id_cave)
    if ok:
        flash("Étagère supprimée ✅", "success")
    else:
        flash("Impossible de supprimer : l’étagère n’est pas vide.", "error")
    return redirect(url_for("ma_cave"))


# ---------------------------------------------------------------------
# Historique & export
# ---------------------------------------------------------------------
@app.route("/historique")
@login_required
def historique():
    """
    Liste l'historique des sorties (archives), rejoint avec bouteille/étagère.
    """
    uid = current_uid()
    with DB() as c:
        moves = c.execute("""
            SELECT a.date, a.quantite, a.motif,
                   b.domaine, b.nom, b.annee, b.type, b.region,
                   COALESCE(e.nom, '(Étagère supprimée)') AS etagere_nom
            FROM sortie_archive a
            LEFT JOIN bouteille b ON b.id_bouteille = a.id_bouteille
            LEFT JOIN etagere  e  ON e.id_etagere   = a.id_etagere
            WHERE a.id_utilisateur = ?
            ORDER BY a.date DESC
        """, (uid,)).fetchall()
    return render_template("historique.html", moves=moves)


# ---------------------------------------------------------------------
# Debug : afficher le plan des routes
# ---------------------------------------------------------------------
@app.get("/_routes")
def _routes():
    """Renvoie toutes les routes Flask (utile en debug intégration)."""
    return "<pre>" + "\n".join(
        f"{r.endpoint:24s}  {','.join(sorted(r.methods)):18s}  {r.rule}"
        for r in app.url_map.iter_rules()
    ) + "</pre>"


# ---------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

# models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
from contextlib import contextmanager
import sqlite3

DB_PATH = "cave.db"

# ---------------------------------------------------------------------
# Accès base (fonction contexte au lieu d'une classe)
# ---------------------------------------------------------------------
@contextmanager
def Database(path: str = DB_PATH):
    """
    Contexte SQLite avec row_factory=Row + commit/rollback auto.
    Compatible avec: `from models import Database as DB` puis `with DB() as c:`
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def ensure_schema():
    """ ajoute des colonnes si manquantes (idempotent)."""
    with Database() as c:
        try:
            c.execute("ALTER TABLE utilisateur ADD COLUMN mot_de_passe TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE utilisateur ADD COLUMN droits TEXT DEFAULT 'standard'")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE sortie_archive ADD COLUMN id_bouteille INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE sortie_archive ADD COLUMN id_etagere INTEGER")
        except Exception:
            pass


# ---------------------------------------------------------------------
# 1) USER / Utilisateur
# ---------------------------------------------------------------------
@dataclass
class Utilisateur:
    id_utilisateur: int
    nom: str
    email: str
    droits: str = "standard"
    mot_de_passe: Optional[str] = None

    # Récupère un utilisateur via son email (login/inscription)
    @staticmethod
    def get_by_email(email: str) -> Optional["Utilisateur"]:
        with Database() as c:
            r = c.execute("SELECT * FROM utilisateur WHERE email=?", (email,)).fetchone()
            return Utilisateur(**dict(r)) if r else None

    # Récupère un utilisateur par identifiant
    @staticmethod
    def get(uid: int) -> Optional["Utilisateur"]:
        with Database() as c:
            r = c.execute("SELECT * FROM utilisateur WHERE id_utilisateur=?", (uid,)).fetchone()
            return Utilisateur(**dict(r)) if r else None

    # Crée un utilisateur et renvoie son id
    @staticmethod
    def create(nom: str, email: str, hash_pwd: str, droits: str = "standard") -> int:
        with Database() as c:
            cur = c.execute(
                "INSERT INTO utilisateur(nom, email, mot_de_passe, droits) VALUES (?,?,?,?)",
                (nom, email, hash_pwd, droits),
            )
            return cur.lastrowid


# ---------------------------------------------------------------------
# 2) CAVE
# ---------------------------------------------------------------------
@dataclass
class Cave:
    id_cave: int
    nom: str
    id_utilisateur: int

    # Récupère la cave associée à un utilisateur
    @staticmethod
    def get_by_user(uid: int) -> Optional["Cave"]:
        with Database() as c:
            r = c.execute("SELECT * FROM cave WHERE id_utilisateur=?", (uid,)).fetchone()
            return Cave(**dict(r)) if r else None

    # Crée une cave pour un utilisateur et renvoie son id
    @staticmethod
    def create_for_user(uid: int, nom: str) -> int:
        with Database() as c:
            cur = c.execute("INSERT INTO cave(nom, id_utilisateur) VALUES (?,?)", (nom, uid))
            return cur.lastrowid


# ---------------------------------------------------------------------
# 3) Etagere
# ---------------------------------------------------------------------
@dataclass
class Etagere:
    id_etagere: int
    id_cave: int
    nom: str
    capacite: int

    # Liste toutes les étagères d'une cave
    @staticmethod
    def list_for_cave(id_cave: int) -> List["Etagere"]:
        with Database() as c:
            rows = c.execute(
                "SELECT * FROM etagere WHERE id_cave=? ORDER BY id_etagere", (id_cave,)
            ).fetchall()
            return [Etagere(**dict(r)) for r in rows]

    # Crée une étagère et renvoie son id
    @staticmethod
    def create(id_cave: int, nom: str, capacite: int) -> int:
        with Database() as c:
            cur = c.execute(
                "INSERT INTO etagere(id_cave, nom, capacite) VALUES (?,?,?)",
                (id_cave, nom, capacite),
            )
            return cur.lastrowid

    # Calcule la capacité restante d'une étagère (places libres)
    @staticmethod
    def capacity_left(id_etagere: int) -> int:
        with Database() as c:
            cap = c.execute(
                "SELECT capacite FROM etagere WHERE id_etagere=?", (id_etagere,)
            ).fetchone()["capacite"]
            used = c.execute(
                "SELECT COALESCE(SUM(quantite),0) q FROM stock_bouteilles WHERE id_etagere=?",
                (id_etagere,),
            ).fetchone()["q"]
            return int(cap - used)

    # Supprime l'étagère si et seulement si elle est vide
    @staticmethod
    def delete_if_empty(id_etagere: int, id_cave: int) -> bool:
        with Database() as c:
            try:
                q = c.execute(
                    "SELECT COALESCE(SUM(quantite),0) q FROM stock_bouteilles WHERE id_etagere=?",
                    (id_etagere,),
                ).fetchone()["q"]
            except sqlite3.OperationalError:
                q = 0
            if q != 0:
                return False
            c.execute("DELETE FROM etagere WHERE id_etagere=? AND id_cave=?", (id_etagere, id_cave))
            return True


# ---------------------------------------------------------------------
# 4) Bouteille
# ---------------------------------------------------------------------
@dataclass
class Bouteille:
    id_bouteille: int
    domaine: str
    nom: str
    type: str
    annee: int
    region: str
    prix: float
    photo: Optional[str] = None

    # Récupère une bouteille par identifiant
    @staticmethod
    def get(bid: int) -> Optional["Bouteille"]:
        with Database() as c:
            r = c.execute("SELECT * FROM bouteille WHERE id_bouteille=?", (bid,)).fetchone()
            return Bouteille(**dict(r)) if r else None

    # Renvoie une liste légère (id, nom, annee, domaine) pour les selects
    @staticmethod
    def list_all_light() -> List[sqlite3.Row]:
        """liste légère pour un <select> (id + nom + millésime + domaine)."""
        with Database() as c:
            return c.execute(
                """
                SELECT id_bouteille, nom, annee, domaine
                FROM bouteille
                ORDER BY nom
                """
            ).fetchall()


# ---------------------------------------------------------------------
# 5) Stock_bouteilles
# ---------------------------------------------------------------------
@dataclass
class Stock_bouteilles:
    id_stock: int
    id_etagere: int
    id_bouteille: int
    quantite: int
    slot: Optional[int] = None

    # Liste le stock (lots) pour l'utilisateur courant, avec jointures utiles
    @staticmethod
    def list_for_user(uid: int):
        with Database() as c:
            return c.execute(
                """
                SELECT
                    s.id_stock,
                    e.id_etagere,
                    e.nom                     AS etagere_nom,
                    e.capacite,
                    CAST(s.slot AS INTEGER)   AS slot,
                    CAST(s.quantite AS INTEGER) AS quantite,
                    b.id_bouteille            AS id_bouteille,
                    b.domaine, b.nom, b.type, b.annee, b.region, b.prix,
                    b.photo                   AS photo
                FROM cave c
                JOIN etagere e               ON e.id_cave      = c.id_cave
                LEFT JOIN stock_bouteilles s ON s.id_etagere   = e.id_etagere
                LEFT JOIN bouteille b        ON b.id_bouteille = s.id_bouteille
                WHERE c.id_utilisateur = ?
                  AND (s.id_stock IS NULL OR s.quantite > 0)
                ORDER BY e.id_etagere, COALESCE(s.slot, 9999)
                """,
                (uid,),
            ).fetchall()

    # Ajoute un lot (sans fusion) dans l'étagère/slot choisis
    @staticmethod
    def add_lot(id_etagere: int, id_bouteille: int, quantite: int, slot: Optional[int]) -> None:
        with Database() as c:
            c.execute(
                "INSERT INTO stock_bouteilles(id_etagere, id_bouteille, quantite, slot) VALUES (?,?,?,?)",
                (id_etagere, id_bouteille, quantite, slot),
            )

    # Ajoute ou incrémente un lot existant si même étagère + bouteille + slot
    @staticmethod
    def add_or_increment(id_etagere: int, id_bouteille: int, quantite: int, slot: int):
        with Database() as c:
            r = c.execute(
                """
                SELECT id_stock, quantite FROM stock_bouteilles
                WHERE id_etagere=? AND id_bouteille=? AND slot=?
                """,
                (id_etagere, id_bouteille, slot),
            ).fetchone()
            if r:
                c.execute(
                    "UPDATE stock_bouteilles SET quantite=quantite+? WHERE id_stock=?",
                    (quantite, r["id_stock"]),
                )
            else:
                c.execute(
                    "INSERT INTO stock_bouteilles(id_etagere, id_bouteille, quantite, slot) VALUES (?,?,?,?)",
                    (id_etagere, id_bouteille, quantite, slot),
                )

    # Donne le prochain slot libre (1..capacite) pour une étagère
    @staticmethod
    def next_free_slot(id_etagere: int, capacite: int) -> int:
        with Database() as c:
            rows = c.execute(
                "SELECT slot FROM stock_bouteilles WHERE id_etagere=?", (id_etagere,)
            ).fetchall()
            taken = {r["slot"] for r in rows if r["slot"] is not None}
        for i in range(1, capacite + 1):
            if i not in taken:
                return i
        return capacite

    # Récupère un lot (stock) par identifiant
    @staticmethod
    def get_lot(id_stock: int) -> Optional["Stock_bouteilles"]:
        with Database() as c:
            r = c.execute("SELECT * FROM stock_bouteilles WHERE id_stock=?", (id_stock,)).fetchone()
            return Stock_bouteilles(**dict(r)) if r else None

    # Décrémente la quantité d'un lot, supprime si elle atteint 0
    @staticmethod
    def decrement(id_stock: int, q: int) -> None:
        with Database() as c:
            r = c.execute(
                "SELECT quantite FROM stock_bouteilles WHERE id_stock=?", (id_stock,)
            ).fetchone()
            if not r:
                raise ValueError("Lot introuvable")
            current = int(r["quantite"])
            if q < 1 or q > current:
                raise ValueError("Quantité invalide.")
            rest = current - q
            if rest == 0:
                c.execute("DELETE FROM stock_bouteilles WHERE id_stock=?", (id_stock,))
            else:
                c.execute(
                    "UPDATE stock_bouteilles SET quantite=? WHERE id_stock=?", (rest, id_stock)
                )

    # Liste les lots sans slot (à ranger) pour l'utilisateur
    @staticmethod
    def list_unassigned_for_user(uid: int):
        with Database() as c:
            return c.execute(
                """
                SELECT s.id_stock, s.id_etagere, s.quantite, s.slot,
                       b.id_bouteille, b.nom, b.domaine, b.type, b.annee, b.region
                FROM cave cv
                JOIN etagere e  ON e.id_cave = cv.id_cave
                JOIN stock_bouteilles s ON s.id_etagere = e.id_etagere
                JOIN bouteille b ON b.id_bouteille = s.id_bouteille
                WHERE cv.id_utilisateur = ? AND s.quantite > 0 AND s.slot IS NULL
                ORDER BY e.id_etagere, b.nom
                """,
                (uid,),
            ).fetchall()

    # Affecte ou modifie le slot d'un lot
    @staticmethod
    def set_slot(id_stock: int, slot: int):
        with Database() as c:
            c.execute("UPDATE stock_bouteilles SET slot=? WHERE id_stock=?", (slot, id_stock))


# ---------------------------------------------------------------------
# 6) SortieArchive
# ---------------------------------------------------------------------
@dataclass
class SortieArchive:
    id_stock: int
    id_utilisateur: int
    id_bouteille: int
    id_etagere: int
    date: Optional[str]
    quantite: int
    motif: str

    # Ajoute une ligne d'archive (sortie de cave) datée à maintenant
    @staticmethod
    def add(
        id_stock: int,
        id_utilisateur: int,
        quantite: int,
        motif: str,
        id_bouteille: int,
        id_etagere: int,
    ) -> None:
        with Database() as c:
            c.execute(
                """
                INSERT INTO sortie_archive(id_stock, id_utilisateur, date, quantite, motif, id_bouteille, id_etagere)
                VALUES (?, ?, DATETIME('now'), ?, ?, ?, ?)
                """,
                (id_stock, id_utilisateur, quantite, motif, id_bouteille, id_etagere),
            )


# ---------------------------------------------------------------------
# 7) Revue
# ---------------------------------------------------------------------
@dataclass
class Revue:
    id_revue: int
    bouteille_id: int
    auteur_id: int
    score: Optional[float]
    commentaire: Optional[str]
    date: Optional[str]

    # Ajoute un avis sur une bouteille et renvoie l'id de l'avis
    @staticmethod
    def add(
        bouteille_id: int, auteur_id: int, score: Optional[float], commentaire: Optional[str]
    ) -> int:
        with Database() as c:
            cur = c.execute(
                'INSERT INTO revue (bouteille_id, auteur_id, score, commentaire, "date") '
                'VALUES (?,?,?,?, DATETIME("now"))',
                (bouteille_id, auteur_id, score, commentaire),
            )
            return cur.lastrowid

    # Liste les avis d'une bouteille avec le nom de l'auteur
    @staticmethod
    def list_for_bottle(bid: int) -> List[sqlite3.Row]:
        with Database() as c:
            return c.execute(
                """
                SELECT r.*, u.nom AS auteur_nom
                FROM revue r
                JOIN utilisateur u ON u.id_utilisateur=r.auteur_id
                WHERE r.bouteille_id=?
                ORDER BY r.date DESC
                """,
                (bid,),
            ).fetchall()

    # Calcule la moyenne des notes d'une bouteille (arrondie à 2 décimales)
    @staticmethod
    def avg_for_bottle(bid: int) -> Optional[float]:
        with Database() as c:
            r = c.execute(
                "SELECT ROUND(AVG(score),2) AS m FROM revue WHERE bouteille_id=?", (bid,)
            ).fetchone()
        return r["m"] if r and r["m"] is not None else None

    # Recherche d'avis communautaires (filtre nom/domaine/région)
    @staticmethod
    def community_reviews(q: str) -> List[sqlite3.Row]:
        """
        Retourne les avis rejoints avec bouteille + auteur.
        Filtre optionnel sur nom/domaine/région (LIKE).
        """
        with Database() as c:
            if q:
                like = f"%{q}%"
                return c.execute(
                    """
                    SELECT r.id_revue, r.score, r.commentaire, r.date,
                           b.id_bouteille, b.nom, b.domaine, b.annee, b.type, b.region,
                           u.nom AS auteur_nom
                    FROM revue r
                    JOIN bouteille b ON b.id_bouteille = r.bouteille_id
                    JOIN utilisateur u ON u.id_utilisateur = r.auteur_id
                    WHERE b.nom LIKE ? OR b.domaine LIKE ? OR b.region LIKE ?
                    ORDER BY r.date DESC
                    LIMIT 200
                    """,
                    (like, like, like),
                ).fetchall()
            else:
                return c.execute(
                    """
                    SELECT r.id_revue, r.score, r.commentaire, r.date,
                           b.id_bouteille, b.nom, b.domaine, b.annee, b.type, b.region,
                           u.nom AS auteur_nom
                    FROM revue r
                    JOIN bouteille b ON b.id_bouteille = r.bouteille_id
                    JOIN utilisateur u ON u.id_utilisateur = r.auteur_id
                    ORDER BY r.date DESC
                    LIMIT 200
                    """
                ).fetchall()

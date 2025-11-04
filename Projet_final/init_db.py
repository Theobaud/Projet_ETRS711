# init_db.py
import sqlite3

DB_FILE = "cave.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Activer les clés étrangères
    cur.execute("PRAGMA foreign_keys = ON;")

    # ========================
    # Schéma (DROP + CREATE)
    # ========================
    cur.executescript("""
    DROP TABLE IF EXISTS revue;
    DROP TABLE IF EXISTS sortie_archive;
    DROP TABLE IF EXISTS stock_bouteilles;
    DROP TABLE IF EXISTS bouteille;
    DROP TABLE IF EXISTS etagere;
    DROP TABLE IF EXISTS cave;
    DROP TABLE IF EXISTS utilisateur;

    CREATE TABLE utilisateur (
        id_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
        nom   TEXT NOT NULL,
        email TEXT NOT NULL
    );

    CREATE TABLE cave (
        id_cave INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        id_utilisateur INTEGER NOT NULL,
        FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
    );

    CREATE TABLE etagere (
        id_etagere INTEGER PRIMARY KEY AUTOINCREMENT,
        id_cave  INTEGER NOT NULL,
        nom      TEXT NOT NULL,
        capacite INTEGER NOT NULL,
        FOREIGN KEY (id_cave) REFERENCES cave(id_cave) ON DELETE CASCADE
    );

    CREATE TABLE bouteille (
        id_bouteille INTEGER PRIMARY KEY AUTOINCREMENT,
        domaine TEXT NOT NULL,
        nom     TEXT NOT NULL,
        type    TEXT NOT NULL,
        annee   INTEGER NOT NULL,
        region  TEXT NOT NULL,
        prix    REAL NOT NULL,
        photo   TEXT
    );

    CREATE TABLE stock_bouteilles (
        id_stock     INTEGER PRIMARY KEY AUTOINCREMENT,
        id_etagere   INTEGER NOT NULL,
        id_bouteille INTEGER NOT NULL,
        quantite     INTEGER NOT NULL,
        slot         INTEGER,
        FOREIGN KEY (id_etagere)   REFERENCES etagere(id_etagere)     ON DELETE CASCADE,
        FOREIGN KEY (id_bouteille) REFERENCES bouteille(id_bouteille) ON DELETE RESTRICT
    );

    CREATE TABLE sortie_archive (
        id_archive     INTEGER PRIMARY KEY AUTOINCREMENT,
        id_stock       INTEGER NOT NULL,
        id_utilisateur INTEGER NOT NULL,
        "date"         TEXT NOT NULL,
        quantite       INTEGER NOT NULL,
        motif          TEXT NOT NULL,  -- ex: BUE/OFFERTE/CASSEE
        FOREIGN KEY (id_stock)       REFERENCES stock_bouteilles(id_stock) ON DELETE CASCADE,
        FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
    );

    -- IMPORTANT : colonnes conformes à app.py (bouteille_id, auteur_id, "date")
    CREATE TABLE revue (
        id_revue     INTEGER PRIMARY KEY AUTOINCREMENT,
        bouteille_id INTEGER NOT NULL,
        auteur_id    INTEGER NOT NULL,
        score        REAL,            -- 0..20 (ou NULL si commentaire seul)
        commentaire  TEXT,
        "date"       TEXT NOT NULL,
        FOREIGN KEY (bouteille_id) REFERENCES bouteille(id_bouteille) ON DELETE CASCADE,
        FOREIGN KEY (auteur_id)    REFERENCES utilisateur(id_utilisateur) ON DELETE CASCADE
    );
    """)

    # ========================
    # Données de départ (seed)
    # ========================
    # Utilisateurs
    cur.execute("INSERT INTO utilisateur (nom, email) VALUES (?,?)", ("Alice", "alice@example.org"))
    cur.execute("INSERT INTO utilisateur (nom, email) VALUES (?,?)", ("Bob",   "bob@example.org"))

    # Caves
    cur.execute("INSERT INTO cave (nom, id_utilisateur) VALUES (?,?)", ("Cave d'Alice", 1))
    cur.execute("INSERT INTO cave (nom, id_utilisateur) VALUES (?,?)", ("Cave de Bob",  2))

    # Étageres
    cur.execute("INSERT INTO etagere (id_cave, nom, capacite) VALUES (?,?,?)", (1, "Étagère A", 10))
    cur.execute("INSERT INTO etagere (id_cave, nom, capacite) VALUES (?,?,?)", (1, "Étagère B",  8))
    cur.execute("INSERT INTO etagere (id_cave, nom, capacite) VALUES (?,?,?)", (2, "Étagère A", 12))

    # Bouteilles
    cur.execute("""INSERT INTO bouteille (domaine, nom, type, annee, region, prix, photo)
                   VALUES (?,?,?,?,?,?,?)""",
                ("Château Margaux", "Margaux", "Rouge", 2015, "Bordeaux", 120.0, None))
    cur.execute("""INSERT INTO bouteille (domaine, nom, type, annee, region, prix, photo)
                   VALUES (?,?,?,?,?,?,?)""",
                ("Domaine Laroche", "Chablis", "Blanc", 2020, "Bourgogne", 22.5, None))

    # Stocks : 3 Margaux en slot 4 (cave Alice / étagère A)
    cur.execute("""INSERT INTO stock_bouteilles (id_etagere, id_bouteille, quantite, slot)
                   VALUES (?,?,?,?)""", (1, 1, 3, 4))

    # Archive : Alice boit 1 Margaux -> on décrémente à la main pour la seed
    cur.execute("""INSERT INTO sortie_archive (id_stock, id_utilisateur, "date", quantite, motif)
                   VALUES (?,?,?,?,?)""", (1, 1, "2025-03-20 20:15:00", 1, "BUE"))
    cur.execute("UPDATE stock_bouteilles SET quantite = quantite - 1 WHERE id_stock = 1")

    # Revues
    cur.execute("""INSERT INTO revue (bouteille_id, auteur_id, score, commentaire, "date")
                   VALUES (?,?,?,?,?)""",
                (1, 1, 15.5, "Très bon, tanins soyeux.", "2025-03-21 10:00:00"))
    cur.execute("""INSERT INTO revue (bouteille_id, auteur_id, score, commentaire, "date")
                   VALUES (?,?,?,?,?)""",
                (2, 2, None, "Frais et salin, parfait l'été.", "2025-03-22 12:00:00"))

    conn.commit()
    conn.close()
    print("✅ Base de données initialisée avec succès :", DB_FILE)

if __name__ == "__main__":
    init_db()

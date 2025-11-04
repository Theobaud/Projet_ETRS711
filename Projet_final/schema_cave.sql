PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- Ré-initialisation
DELETE FROM revue;
DELETE FROM sortie_archive;
DELETE FROM stock_bouteilles;
DELETE FROM etagere;
DELETE FROM bouteille;
DELETE FROM cave;
DELETE FROM utilisateur;

-- =========================
-- UTILISATEURS
-- =========================
INSERT INTO utilisateur (nom, email) VALUES
('Alice Martin','alice@example.org'),
('Lucas Durand','lucas@example.org'),
('Emma Bernard','emma@example.org');

-- =========================
-- CAVES (1 par utilisateur)
-- =========================
INSERT INTO cave (nom, id_utilisateur) VALUES
('Cave d''Alice', 1),
('Cave de Lucas', 2),
('Cave d''Emma', 3);

-- =========================
-- ETAGERES
-- =========================
INSERT INTO etagere (id_cave, nom, capacite) VALUES
(1,'Étagère A',10),
(1,'Étagère B',8),
(2,'Étagère A',12),
(3,'Étagère A',6);

-- =========================
-- BOUTEILLES (Vins)
-- =========================
INSERT INTO bouteille (domaine, nom, type, annee, region, prix, photo) VALUES
('Château Margaux','Margaux','Rouge',2015,'Bordeaux',120.0,NULL),
('Chablis Domaine Laroche','Chablis','Blanc',2020,'Bourgogne',22.5,NULL),
('Château Montelena','Cabernet Sauvignon','Rouge',2016,'Napa Valley',75.0,NULL),
('Domaine Tempier','Bandol Rosé','Rosé',2023,'Provence',28.0,NULL);

-- =========================
-- STOCK (lots identiques)
-- =========================
-- Alice : 3 Margaux en slot 4, 6 Chablis en slot 7
INSERT INTO stock_bouteilles (id_etagere, id_bouteille, quantite, slot) VALUES
(1, 1, 3, 4),
(1, 2, 6, 7);

-- Lucas : 4 Montelena (slot 1)
INSERT INTO stock_bouteilles (id_etagere, id_bouteille, quantite, slot) VALUES
(3, 3, 4, 1);

-- Emma : 5 Bandol Rosé (slot 2)
INSERT INTO stock_bouteilles (id_etagere, id_bouteille, quantite, slot) VALUES
(4, 4, 5, 2);

-- =========================
-- ARCHIVES (exemple simple)
-- =========================
-- Alice boit 1 Margaux (on suppose id_stock=1)
INSERT INTO sortie_archive (id_stock, id_utilisateur, date, quantite, motif)
VALUES (1, 1, '2025-03-20 20:15:00', 1, 'BUE');

UPDATE stock_bouteilles SET quantite = quantite - 1 WHERE id_stock = 1;

-- =========================
-- REVUES (notes/commentaires)
-- =========================
-- Revue d'Alice après Margaux
INSERT INTO revue (bouteille_id, auteur_id, score, commentaire, date)
VALUES (1, 1, 15.5, 'Très bon, tanins soyeux.', '2025-03-21 10:00:00');

-- Revue d'Emma sur Bandol (commentaire seul)
INSERT INTO revue (bouteille_id, auteur_id, score, commentaire, date)
VALUES (4, 3, NULL, 'Frais et salin, parfait pour l''été.', '2025-03-23 12:30:00');

COMMIT;

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
INSERT INTO utilisateur (nom, email, date_inscription) VALUES
('Alice Martin','alice@example.org','2024-09-05'),
('Lucas Durand','lucas@example.org','2024-10-12'),
('Emma Bernard','emma@example.org','2023-11-20');

-- =========================
-- CAVES (1 par utilisateur)
-- =========================
INSERT INTO cave (nom, proprietaire_id) VALUES
('Cave d''Alice', 1),
('Cave de Lucas', 2),
('Cave d''Emma', 3);

-- =========================
-- ETAGERES
-- =========================
INSERT INTO etagere (cave_id, nom, capacite) VALUES
(1,'Étagère A',10),
(1,'Étagère B',8),
(2,'Étagère A',12),
(3,'Étagère A',6);

-- =========================
-- BOUTEILLES (Vins)
-- =========================
INSERT INTO bouteille (domaine, nom, type, annee, region, prix_eur, photo_url) VALUES
('Château Margaux','Margaux','Rouge',2015,'Bordeaux',120.0,NULL),
('Chablis Domaine Laroche','Chablis','Blanc',2020,'Bourgogne',22.5,NULL),
('Château Montelena','Cabernet Sauvignon','Rouge',2016,'Napa Valley',75.0,NULL),
('Domaine Tempier','Bandol Rosé','Rosé',2023,'Provence',28.0,NULL);

-- =========================
-- STOCK (lots identiques)
-- =========================
-- Alice : 3 Margaux en slot 4, 6 Chablis en slot 7
INSERT INTO stock_bouteilles (etagere_id, bouteille_id, quantite, slot) VALUES
(1, 1, 3, 4),
(1, 2, 6, 7);

-- Lucas : 4 Montelena (slot 1)
INSERT INTO stock_bouteilles (etagere_id, bouteille_id, quantite, slot) VALUES
(3, 3, 4, 1);

-- Emma : 5 Bandol Rosé (slot 2)
INSERT INTO stock_bouteilles (etagere_id, bouteille_id, quantite, slot) VALUES
(4, 4, 5, 2);

-- =========================
-- ARCHIVES (boire/consommer)
-- =========================
-- Alice boit 1 Margaux
INSERT INTO sortie_archive (stock_id, auteur_id, date_sortie, quantite, motif)
VALUES (1, 1, '2025-03-20 20:15:00', 1, 'BUE');

-- On décrémente manuellement le stock (si on rejoue la seed)
UPDATE stock_bouteilles SET quantite = quantite - 1 WHERE id_stock = 1;

-- Lucas offre 1 Montelena
INSERT INTO sortie_archive (stock_id, auteur_id, date_sortie, quantite, motif)
VALUES (3, 2, '2025-03-22 19:00:00', 1, 'OFFERTE');
UPDATE stock_bouteilles SET quantite = quantite - 1 WHERE id_stock = 3;

-- Revue d'Alice après avoir bu Margaux (archive 1)
INSERT INTO revue (bouteille_id, auteur_id, archive_id, score, commentaire, date_revue)
VALUES (1, 1, 1, 15.5, 'Très bon, tanins soyeux.', '2025-03-21 10:00:00');

-- Revue d'Emma sur Bandol (sans archive, commentaire seul)
INSERT INTO revue (bouteille_id, auteur_id, score, commentaire, date_revue)
VALUES (4, 3, NULL, 'Frais et salin, parfait pour l''été.', '2025-03-23 12:30:00');

COMMIT;

#!/bin/bash
# Remise à neuf quotidienne de l'instance en ligne, lancée par deploiement.middleware.RemiseQuotidienne
# à la première visite après 3 h (heure de Nouméa). Copie de travail : ~/remise_a_zero.sh.
# Repart de la base de référence compressée ~/db.initial.sqlite3.gz en conservant le compteur d'audience.
# Sans copie temporaire de la base : le compte gratuit n'a que 512 Mo de disque.
set -euo pipefail
cd ~/plateforme-multisite-wagtail-nc
sqlite3 db.sqlite3 ".mode insert suivi_pagevue" "SELECT * FROM suivi_pagevue;" > ~/vues.sql
gunzip -c ~/db.initial.sqlite3.gz > db.sqlite3
sqlite3 db.sqlite3 "DELETE FROM suivi_pagevue;"
sqlite3 db.sqlite3 < ~/vues.sql
rm -f ~/vues.sql
echo "$(date -u +%FT%TZ) remise à neuf faite ($(sqlite3 db.sqlite3 'SELECT count(*) FROM suivi_pagevue') compteurs conservés)"

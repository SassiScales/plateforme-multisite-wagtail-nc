#!/bin/bash
# Remise à neuf nocturne de l'instance en ligne (tâche planifiée PythonAnywhere, 16:00 UTC = 3 h à Nouméa).
# Repart de la base de référence ~/db.initial.sqlite3 en conservant le compteur d'audience.
set -euo pipefail
cd ~/plateforme-multisite-wagtail-nc
cp ~/db.initial.sqlite3 db.tmp.sqlite3
sqlite3 db.tmp.sqlite3 "ATTACH 'db.sqlite3' AS ancien; DELETE FROM suivi_pagevue; INSERT INTO suivi_pagevue SELECT * FROM ancien.suivi_pagevue;"
mv db.tmp.sqlite3 db.sqlite3
touch /var/www/sassiscales_pythonanywhere_com_wsgi.py
echo "$(date -u +%FT%TZ) remise à neuf faite"

#!/bin/bash
# Zieht die Volant-Patch-Dateien aus christianh17/ha-warema-wms (main-Branch)
# und kopiert sie an die richtige Stelle in custom_components/warema_wms.
#
# Manuell ausführen: bash /config/scripts/update_warema_wms_valance_patch.sh
# Danach: Home Assistant neu starten.

set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/christianh17/ha-warema-wms/main"
TARGET="/config/custom_components/warema_wms"

echo "Lade aktuelle Dateien von christianh17/ha-warema-wms (main) ..."

curl -fsSL "${REPO_RAW}/custom_components/warema_wms/__init__.py" \
    -o "${TARGET}/__init__.py"

curl -fsSL "${REPO_RAW}/custom_components/warema_wms/coordinator.py" \
    -o "${TARGET}/coordinator.py"

curl -fsSL "${REPO_RAW}/custom_components/warema_wms/services.yaml" \
    -o "${TARGET}/services.yaml"

curl -fsSL "${REPO_RAW}/custom_components/warema_wms/pywarema/protocol.py" \
    -o "${TARGET}/pywarema/protocol.py"

curl -fsSL "${REPO_RAW}/custom_components/warema_wms/pywarema/stick.py" \
    -o "${TARGET}/pywarema/stick.py"

echo "Fertig. Bitte Home Assistant neu starten, damit die Aenderungen greifen."

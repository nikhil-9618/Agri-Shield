#!/usr/bin/env bash
# Advisory content is authored once in advisory/ and bundled into the app so the
# farmer can read saved guidance offline. Run after editing advisory content.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf mobile/assets/advisory
mkdir -p mobile/assets/advisory
cp -r advisory/* mobile/assets/advisory/
echo "Synced $(ls mobile/assets/advisory/diseases | wc -l) disease files into mobile/assets/advisory"

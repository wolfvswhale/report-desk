#!/usr/bin/env bash
# Copy the generator into the Hugging Face Space repo and push it.
# The Space is a git repo of its own; this keeps it from drifting.
#
#   ./scripts/sync-space.sh "a note about what changed"
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SPACE_DIR="$HOME/Desktop/report-desk-space"
MESSAGE="${1:-sync generator from the app repo}"

if [ ! -d "$SPACE_DIR/.git" ]; then
  echo "No Space checkout at $SPACE_DIR — clone it first."
  exit 1
fi

cp "$APP_DIR/api/generate.py"        "$SPACE_DIR/generate.py"
cp "$APP_DIR/api/radon_report.py"    "$SPACE_DIR/radon_report.py"
cp "$APP_DIR/requirements.txt"       "$SPACE_DIR/requirements.txt"
cp "$APP_DIR/space/Dockerfile"       "$SPACE_DIR/Dockerfile"
cp "$APP_DIR/space/README.md"        "$SPACE_DIR/README.md"

cd "$SPACE_DIR"
git add -A
if git diff --cached --quiet; then
  echo "Nothing changed."
  exit 0
fi
git commit -q -m "$MESSAGE"
git push -q
echo "Pushed. The Space rebuilds itself — takes a couple of minutes."

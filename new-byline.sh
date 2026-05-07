#!/bin/bash
# new-byline.sh — add a published byline
# Usage: ./new-byline.sh "Publication Name" "Article Title" "https://url" "YYYY-MM-DD"

set -e

if [ -z "$3" ]; then
  echo "Usage: ./new-byline.sh \"Publication Name\" \"Article Title\" \"https://url\" \"YYYY-MM-DD\""
  echo "Date is optional. Example:"
  echo "  ./new-byline.sh \"Sacramento Bee\" \"How Silicon Valley Lost Its Factories\" \"https://sacbee.com/...\" \"2026-04-01\""
  exit 1
fi

PUB="$1"
TITLE="$2"
URL="$3"
DATE="${4:-}"

# Escape single quotes
PUB_ESC=$(echo "$PUB" | sed "s/'/\\\\'/g")
TITLE_ESC=$(echo "$TITLE" | sed "s/'/\\\\'/g")
URL_ESC=$(echo "$URL" | sed "s/'/\\\\'/g")

# Build the new entry line
if [ -n "$DATE" ]; then
  NEW_ENTRY="  { title: '${TITLE_ESC}', publication: '${PUB_ESC}', url: '${URL_ESC}', date: '${DATE}' },"
else
  NEW_ENTRY="  { title: '${TITLE_ESC}', publication: '${PUB_ESC}', url: '${URL_ESC}', date: '' },"
fi

# Prepend to bylines array (after "var BYLINES = [" line)
TMPFILE=$(mktemp)
awk -v entry="$NEW_ENTRY" '
  /^var BYLINES = \[/ { print; print entry; next }
  { print }
' bylines.js > "$TMPFILE"
mv "$TMPFILE" bylines.js

echo "Added byline: \"${TITLE}\" — ${PUB}"

# Git commit and push
git add bylines.js
git commit -m "byline: ${TITLE} (${PUB})"
git push

echo "Done. Byline live on site."

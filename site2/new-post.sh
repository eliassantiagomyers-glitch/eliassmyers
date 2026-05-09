#!/bin/bash
# new-post.sh — create and publish a new blog post
# Usage: ./new-post.sh "Your Post Title"

set -e

if [ -z "$1" ]; then
  echo "Usage: ./new-post.sh \"Your Post Title\""
  exit 1
fi

TITLE="$1"
DATE=$(date +%Y-%m-%d)

# Make slug from title: lowercase, spaces to hyphens, strip special chars
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]//g' | sed 's/ \+/-/g' | sed 's/^-\+\|-\+$//g')

POST_FILE="posts/${SLUG}.html"

if [ -f "$POST_FILE" ]; then
  echo "Error: $POST_FILE already exists. Pick a different title or slug."
  exit 1
fi

# Create the post HTML file
cat > "$POST_FILE" << HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${TITLE} &mdash; Elias S. Myers</title>
  <link rel="stylesheet" href="../style.css">
</head>
<body>
<div id="wrap">

  <header id="site-header">
    <h1><a href="../index.html" style="text-decoration:none;color:inherit;">Elias S. Myers</a></h1>
    <nav>
      <a href="../index.html">Home</a>
      <a href="../bylines.html">Bylines</a>
      <a href="../blog.html" class="active">Blog</a>
    </nav>
  </header>

  <div class="post-header">
    <h1>${TITLE}</h1>
    <p class="post-meta">${DATE}</p>
  </div>

  <div class="post-body">
    <p>Write your post here.</p>
  </div>

  <div class="post-nav">
    <span></span>
    <span></span>
  </div>

  <footer id="site-footer">
    &copy; Elias S. Myers &mdash;
    <a href="mailto:eliassantiagomyers@berkeley.edu">eliassantiagomyers@berkeley.edu</a>
  </footer>

</div>
</body>
</html>
HTMLEOF

echo "Created: $POST_FILE"

# Open in editor
EDITOR="${EDITOR:-nano}"
$EDITOR "$POST_FILE"

# After editor closes, extract a rough excerpt from the post body (first <p> text)
EXCERPT=$(grep -o '<p>[^<]*' "$POST_FILE" | head -1 | sed 's/<p>//' | cut -c1-200)
if [ -z "$EXCERPT" ]; then
  EXCERPT="..."
fi

# Escape single quotes for JS
TITLE_ESC=$(echo "$TITLE" | sed "s/'/\\\\'/g")
EXCERPT_ESC=$(echo "$EXCERPT" | sed "s/'/\\\\'/g")

# Prepend new entry to posts.js
TMPFILE=$(mktemp)
head -3 posts.js > "$TMPFILE"  # keep the comment header and "var POSTS = ["
echo "  { title: '${TITLE_ESC}', date: '${DATE}', slug: '${SLUG}', excerpt: '${EXCERPT_ESC}' }," >> "$TMPFILE"
tail -n +4 posts.js >> "$TMPFILE"
mv "$TMPFILE" posts.js

echo "Updated: posts.js"

# Git commit and pushbu
git add "posts/${SLUG}.html" posts.js
git commit -m "post: ${TITLE}"
git push origin main

echo ""
echo "Done. Post live at: posts/${SLUG}.html"

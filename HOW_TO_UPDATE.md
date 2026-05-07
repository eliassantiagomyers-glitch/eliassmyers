# How to update the site

## Publish a new blog post

```bash
./new-post.sh "Your Post Title"
```

This creates the HTML file, opens it in your terminal editor (nano by default, or set `EDITOR=vim` etc.), then commits and pushes to GitHub when you save and close. The post will be live within about a minute.

To use a different editor permanently, add this to your `~/.zshrc` or `~/.bash_profile`:

```bash
export EDITOR=nano   # or vim, micro, etc.
```

---

## Add a byline

```bash
./new-byline.sh "Publication Name" "Article Title" "https://full-url" "YYYY-MM-DD"
```

Date is optional. Example:

```bash
./new-byline.sh "Sacramento Bee" "How Silicon Valley Lost Its Factories" "https://sacbee.com/article/..." "2026-04-01"
```

Bylines appear newest-first on the site.

---

## Edit an existing post

Just open the file in `posts/`, edit it, then:

```bash
git add posts/your-post-slug.html
git commit -m "edit: post title"
git push
```

---

## Edit your bio

Open `index.html`, find the `<p class="bio">` section, edit, then commit and push.

---

## Custom domain setup (one time)

1. Buy your domain (Namecheap or Cloudflare Registrar recommended).
2. In your domain's DNS settings, add:
   - Type: `CNAME` | Host: `www` | Value: `eliassantiagomyers-glitch.github.io`
   - Type: `A` | Host: `@` | Value: `185.199.108.153`
   - Type: `A` | Host: `@` | Value: `185.199.109.153`
   - Type: `A` | Host: `@` | Value: `185.199.110.153`
   - Type: `A` | Host: `@` | Value: `185.199.111.153`
3. In your GitHub repo settings → Pages → Custom domain, enter your domain.
4. Check "Enforce HTTPS" once it propagates (can take up to 24 hours).

---

## File structure

```
/
├── index.html       — landing page
├── bylines.html     — all bylines
├── blog.html        — all blog posts
├── style.css        — all styles
├── posts.js         — blog post index data
├── bylines.js       — bylines data
├── new-post.sh      — CLI: publish new post
├── new-byline.sh    — CLI: add byline
└── posts/
    └── *.html       — individual post pages
```

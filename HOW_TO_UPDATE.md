# How to Update Your Portfolio

Since your site is a static site hosted on GitHub Pages, adding new articles involves updating the data file locally and then pushing those changes to GitHub.

## 1. Add a New Article
I've created a simple tool to help you add articles without editing code manually.

1.  Open your terminal (Terminal.app).
2.  Navigate to your website folder:
    ```bash
    cd /Users/eliasmyers/website
    ```
    *(Or wherever you store the project on your computer)*

3.  Run the add command with the link:
    ```bash
    python3 scripts/add_article.py "https://example.com/your-new-article"
    ```

4.  **Follow the prompts**:
    - The script will try to find the Title, Source, and Date automatically.
    - If it's correct, type `y` and hit Enter.
    - If not, you can type the correct details when asked.

This will automatically add the new article to the top of the list in `articles.js`.

## 2. Publish Changes
Once you've added the articles locally, you need to send the changes to GitHub.

1.  **Stage and Commit**:
    ```bash
    git add articles.js
    git commit -m "Add new article: [Article Name]"
    ```

2.  **Push to GitHub**:
    ```bash
    git push origin main
    ```

After a minute or two, GitHub Pages will automatically update your live site!

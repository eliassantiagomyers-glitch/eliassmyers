document.addEventListener('DOMContentLoaded', () => {
    const articlesContainer = document.getElementById('articles-container');

    // Function to render an article
    function renderArticle(article) {
        const articleEl = document.createElement('article');
        articleEl.className = 'work-item';

        articleEl.innerHTML = `
            <div class="work-meta">${article.source} &bull; ${article.date}</div>
            <h2 class="work-heading serif">
                <a href="${article.url}" target="_blank">${article.title}</a>
            </h2>
        `;
        return articleEl;
    }

    // Display articles from global variable
    const articles = window.articles || [];

    if (articles.length === 0) {
        articlesContainer.innerHTML = '<p style="text-align:center">No articles found.</p>';
        return;
    }

    articles.forEach(article => {
        const articleNode = renderArticle(article);
        articlesContainer.appendChild(articleNode);
    });

    // Render Blog Posts (New)
    const posts = window.posts || [];
    const blogContainer = document.getElementById('blog-container');

    if (posts.length > 0 && blogContainer) {
        // Add a "Blog" header if posts exist
        const header = document.createElement('h3');
        header.textContent = "Writing";
        header.style.textAlign = "center"; // Or match styling of featured works
        header.style.marginBottom = "3rem";
        header.style.fontSize = "1.5rem";
        header.style.fontWeight = "bold";
        header.style.textTransform = "uppercase";
        header.style.letterSpacing = "0.1em";
        blogContainer.appendChild(header);

        posts.forEach(post => {
            const postEl = document.createElement('article');
            postEl.className = 'work-item'; // Reuse existing class for consistent spacing
            postEl.innerHTML = `
                <div class="work-meta">${post.date}</div>
                <h2 class="work-heading serif" style="margin-bottom: 1rem;">
                    ${post.title}
                </h2>
                <div class="blog-body" style="font-family: inherit; font-size: 1.1rem; line-height: 1.6;">
                    ${post.body}
                </div>
            `;
            blogContainer.appendChild(postEl);
        });
    }
});

console.log('Portfolio loaded with dynamic articles.');

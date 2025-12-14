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
});

console.log('Portfolio loaded with dynamic articles.');

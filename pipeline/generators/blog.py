"""
Blog post HTML generator

Transforms analyzed content into styled HTML blog posts.
"""
from typing import Dict, Any, Optional, List
import json
from datetime import datetime

from .base import (
    BaseGenerator,
    GeneratedContent,
    ContentFormat,
    GenerationError,
    FetchError,
    DatabaseError
)


class BlogGenerator(BaseGenerator):
    """
    Concrete implementation of blog post generator

    Generates responsive HTML blog posts with:
    - Clean, readable typography
    - Syntax highlighting for metrics
    - Mobile-friendly layout
    - Social sharing metadata
    """

    def __init__(self, config, db_connection=None, logger=None):
        """Initialize blog generator"""
        super().__init__(config, db_connection, logger)

        if self.logger:
            self.logger.info("Initialized BlogGenerator")

    def fetch_content(self, content_id: str) -> Dict[str, Any]:
        """
        Fetch analyzed content from database

        Args:
            content_id: Database ID of content

        Returns:
            Dictionary with content fields

        Raises:
            FetchError: If fetching fails
        """
        if not self.db_connection:
            raise FetchError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            # Fetch content with filing and company info
            cursor.execute("""
                SELECT
                    c.tldr_headline,
                    c.tldr_summary,
                    c.tldr_key_points,
                    c.deep_headline,
                    c.deep_intro,
                    c.deep_sections,
                    c.deep_conclusion,
                    c.key_metrics,
                    c.sentiment_score,
                    c.risk_factors,
                    c.opportunities,
                    c.published_at,
                    f.ticker,
                    f.filing_type,
                    f.fiscal_year,
                    f.fiscal_period,
                    f.filing_date,
                    co.name as company_name
                FROM content c
                JOIN filings f ON c.filing_id = f.id
                JOIN companies co ON f.ticker = co.ticker
                WHERE c.id = %s
            """, (content_id,))

            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise FetchError(f"Content {content_id} not found")

            return {
                'tldr_headline': row[0],
                'tldr_summary': row[1],
                'tldr_key_points': row[2],
                'deep_headline': row[3],
                'deep_intro': row[4],
                'deep_sections': json.loads(row[5]) if row[5] else [],
                'deep_conclusion': row[6],
                'key_metrics': json.loads(row[7]) if row[7] else {},
                'sentiment_score': row[8],
                'risk_factors': row[9] or [],
                'opportunities': row[10] or [],
                'published_at': row[11],
                'ticker': row[12],
                'filing_type': row[13],
                'fiscal_year': row[14],
                'fiscal_period': row[15],
                'filing_date': row[16],
                'company_name': row[17]
            }

        except Exception as e:
            raise FetchError(f"Failed to fetch content: {e}")

    def generate(
        self,
        content_id: str,
        format: ContentFormat,
        options: Optional[Dict[str, Any]] = None
    ) -> GeneratedContent:
        """
        Generate blog post HTML

        Args:
            content_id: Database ID of content
            format: Output format (must be BLOG_POST_HTML)
            options: Format options (include_toc, style)

        Returns:
            GeneratedContent with HTML

        Raises:
            GenerationError: If generation fails
        """
        if format != ContentFormat.BLOG_POST_HTML:
            raise GenerationError(f"Unsupported format: {format}")

        options = options or {}
        include_toc = options.get('include_toc', True)
        style = options.get('style', 'default')

        try:
            # Fetch content
            content = self.fetch_content(content_id)

            # Generate HTML
            html = self._generate_html(content, include_toc, style)

            # Calculate metadata
            word_count = len(html.split())
            reading_time = max(1, word_count // 200)  # 200 words per minute

            metadata = {
                'word_count': word_count,
                'reading_time_minutes': reading_time,
                'style': style,
                'include_toc': include_toc
            }

            return GeneratedContent(
                content_id=content_id,
                format=ContentFormat.BLOG_POST_HTML,
                output=html,
                metadata=metadata
            )

        except Exception as e:
            raise GenerationError(f"Failed to generate blog post: {e}")

    def _generate_html(
        self,
        content: Dict[str, Any],
        include_toc: bool,
        style: str
    ) -> str:
        """Generate complete HTML blog post"""

        # Build sections list for TOC
        sections = content.get('deep_sections', [])

        # Sentiment indicator
        sentiment = content.get('sentiment_score', 0)
        sentiment_class = 'positive' if sentiment > 0.2 else 'negative' if sentiment < -0.2 else 'neutral'
        sentiment_text = 'Positive' if sentiment > 0.2 else 'Negative' if sentiment < -0.2 else 'Neutral'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{content['deep_headline']} | 10KAY</title>
    <meta name="description" content="{content['tldr_summary'][:160]}">
    <style>
        {self._get_css(style)}
    </style>
</head>
<body>
    <article class="blog-post">
        <header class="post-header">
            <div class="meta-info">
                <span class="ticker">{content['ticker']}</span>
                <span class="separator">•</span>
                <span class="filing-type">{content['filing_type']}</span>
                <span class="separator">•</span>
                <span class="fiscal-period">{content['fiscal_period']} {content['fiscal_year']}</span>
                <span class="separator">•</span>
                <span class="sentiment sentiment-{sentiment_class}">{sentiment_text}</span>
            </div>

            <h1 class="headline">{content['deep_headline']}</h1>

            <div class="post-meta">
                <time datetime="{content['published_at'].isoformat() if content['published_at'] else ''}" class="publish-date">
                    {content['published_at'].strftime('%B %d, %Y') if content['published_at'] else 'Draft'}
                </time>
                <span class="separator">•</span>
                <span class="reading-time">{len(content['deep_intro'].split()) // 200 + len(content['deep_conclusion'].split()) // 200} min read</span>
            </div>
        </header>

        <!-- TLDR Section -->
        <aside class="tldr-box">
            <h2 class="tldr-title">TL;DR</h2>
            <p class="tldr-summary">{content['tldr_summary']}</p>
            <ul class="tldr-points">
                {''.join(f'<li>{point}</li>' for point in content['tldr_key_points'])}
            </ul>
        </aside>

        <!-- Key Metrics -->
        {self._render_metrics(content.get('key_metrics', {}))}

        <!-- Table of Contents -->
        {self._render_toc(sections) if include_toc and sections else ''}

        <!-- Introduction -->
        <div class="intro">
            {self._format_text_to_html(content['deep_intro'])}
        </div>

        <!-- Main Sections -->
        <div class="main-content">
            {self._render_sections(sections)}
        </div>

        <!-- Risks & Opportunities -->
        {self._render_risks_opportunities(content.get('risk_factors', []), content.get('opportunities', []))}

        <!-- Conclusion -->
        <div class="conclusion">
            <h2>Bottom Line</h2>
            {self._format_text_to_html(content['deep_conclusion'])}
        </div>

        <!-- Footer -->
        <footer class="post-footer">
            <div class="company-info">
                <strong>{content['company_name']}</strong> ({content['ticker']})
            </div>
            <div class="filing-info">
                Filed {content['filing_date'].strftime('%B %d, %Y')}
            </div>
        </footer>
    </article>
</body>
</html>"""

        return html

    def _get_css(self, style: str) -> str:
        """Get CSS styles for blog post"""
        return """
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            background: #ffffff;
            padding: 2rem 1rem;
        }

        .blog-post {
            max-width: 720px;
            margin: 0 auto;
        }

        .post-header {
            margin-bottom: 3rem;
        }

        .meta-info {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            color: #666;
            margin-bottom: 1rem;
        }

        .ticker {
            font-weight: 600;
            color: #0066cc;
        }

        .separator {
            color: #ccc;
        }

        .sentiment {
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .sentiment-positive {
            background: #d4edda;
            color: #155724;
        }

        .sentiment-negative {
            background: #f8d7da;
            color: #721c24;
        }

        .sentiment-neutral {
            background: #e2e3e5;
            color: #383d41;
        }

        .headline {
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 1rem;
            color: #000;
        }

        .post-meta {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            color: #666;
        }

        .tldr-box {
            background: #f8f9fa;
            border-left: 4px solid #0066cc;
            padding: 1.5rem;
            margin: 2rem 0;
        }

        .tldr-title {
            font-size: 1rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #0066cc;
            margin-bottom: 1rem;
        }

        .tldr-summary {
            font-size: 1.125rem;
            margin-bottom: 1rem;
            color: #333;
        }

        .tldr-points {
            list-style: none;
            padding-left: 0;
        }

        .tldr-points li {
            padding-left: 1.5rem;
            margin-bottom: 0.5rem;
            position: relative;
        }

        .tldr-points li:before {
            content: "→";
            position: absolute;
            left: 0;
            color: #0066cc;
            font-weight: 700;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 2rem 0;
        }

        .metric-card {
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 1rem;
        }

        .metric-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #666;
            margin-bottom: 0.5rem;
        }

        .metric-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: #000;
        }

        .toc {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 2rem 0;
        }

        .toc h2 {
            font-size: 1rem;
            margin-bottom: 1rem;
        }

        .toc ol {
            list-style-position: inside;
        }

        .toc li {
            margin-bottom: 0.5rem;
        }

        .toc a {
            color: #0066cc;
            text-decoration: none;
        }

        .toc a:hover {
            text-decoration: underline;
        }

        .intro, .main-content, .conclusion {
            margin: 2rem 0;
        }

        h2 {
            font-size: 1.75rem;
            font-weight: 700;
            margin: 2.5rem 0 1rem 0;
            color: #000;
        }

        h3 {
            font-size: 1.25rem;
            font-weight: 600;
            margin: 1.5rem 0 0.75rem 0;
            color: #333;
        }

        p {
            margin-bottom: 1.25rem;
            font-size: 1.0625rem;
            line-height: 1.7;
        }

        .risk-opp-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin: 2rem 0;
        }

        .risk-box, .opp-box {
            padding: 1.5rem;
            border-radius: 8px;
        }

        .risk-box {
            background: #fff5f5;
            border-left: 4px solid #e53e3e;
        }

        .opp-box {
            background: #f0fff4;
            border-left: 4px solid #38a169;
        }

        .risk-box h3, .opp-box h3 {
            margin-top: 0;
        }

        .risk-box ul, .opp-box ul {
            list-style: none;
            padding-left: 0;
        }

        .risk-box li, .opp-box li {
            padding-left: 1.5rem;
            margin-bottom: 0.5rem;
            position: relative;
        }

        .risk-box li:before {
            content: "⚠";
            position: absolute;
            left: 0;
        }

        .opp-box li:before {
            content: "✓";
            position: absolute;
            left: 0;
            color: #38a169;
        }

        .post-footer {
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 0.875rem;
        }

        @media (max-width: 768px) {
            .headline {
                font-size: 1.75rem;
            }

            .risk-opp-grid {
                grid-template-columns: 1fr;
                gap: 1rem;
            }

            .metrics-grid {
                grid-template-columns: 1fr;
            }
        }
        """

    def _render_metrics(self, metrics: Dict[str, Any]) -> str:
        """Render key metrics grid"""
        if not metrics:
            return ''

        cards = []
        for label, value in metrics.items():
            # Format label
            label_formatted = label.replace('_', ' ').title()

            cards.append(f"""
                <div class="metric-card">
                    <div class="metric-label">{label_formatted}</div>
                    <div class="metric-value">{value}</div>
                </div>
            """)

        return f"""
        <div class="metrics-grid">
            {''.join(cards)}
        </div>
        """

    def _render_toc(self, sections: List[Dict[str, str]]) -> str:
        """Render table of contents"""
        items = []
        for i, section in enumerate(sections, 1):
            slug = section['title'].lower().replace(' ', '-')
            items.append(f'<li><a href="#{slug}">{section["title"]}</a></li>')

        return f"""
        <nav class="toc">
            <h2>In This Analysis</h2>
            <ol>
                {''.join(items)}
            </ol>
        </nav>
        """

    def _render_sections(self, sections: List[Dict[str, str]]) -> str:
        """Render main content sections"""
        html_sections = []

        for section in sections:
            slug = section['title'].lower().replace(' ', '-')
            html_sections.append(f"""
                <section id="{slug}">
                    <h2>{section['title']}</h2>
                    {self._format_text_to_html(section['content'])}
                </section>
            """)

        return '\n'.join(html_sections)

    def _render_risks_opportunities(self, risks: List[str], opportunities: List[str]) -> str:
        """Render risks and opportunities boxes"""
        if not risks and not opportunities:
            return ''

        html = '<div class="risk-opp-grid">'

        if risks:
            html += f"""
                <div class="risk-box">
                    <h3>Key Risks</h3>
                    <ul>
                        {''.join(f'<li>{risk}</li>' for risk in risks)}
                    </ul>
                </div>
            """

        if opportunities:
            html += f"""
                <div class="opp-box">
                    <h3>Key Opportunities</h3>
                    <ul>
                        {''.join(f'<li>{opp}</li>' for opp in opportunities)}
                    </ul>
                </div>
            """

        html += '</div>'
        return html

    def _format_text_to_html(self, text: str) -> str:
        """Convert plain text to HTML paragraphs"""
        if not text:
            return ''

        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        return '\n'.join(f'<p>{p}</p>' for p in paragraphs)

    def save_to_database(
        self,
        content_id: str,
        generated: GeneratedContent
    ):
        """
        Update content record with blog HTML

        Args:
            content_id: Database ID of content
            generated: GeneratedContent to save

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                UPDATE content
                SET blog_html = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
            """, (
                generated.output,
                json.dumps({'blog_generation': generated.metadata}),
                content_id
            ))

            self.db_connection.commit()
            cursor.close()

            if self.logger:
                self.logger.info(
                    f"Saved blog HTML to database",
                    extra={'content_id': content_id}
                )

        except Exception as e:
            self.db_connection.rollback()
            raise DatabaseError(f"Failed to save blog HTML: {e}")

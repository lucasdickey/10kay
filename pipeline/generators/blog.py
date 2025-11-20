"""
Blog post HTML generator

Transforms analyzed content into styled HTML blog posts.
"""
from typing import Dict, Any, Optional, List
import json
import re
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
                    c.executive_summary,
                    c.key_takeaways,
                    c.deep_dive_opportunities,
                    c.deep_dive_risks,
                    c.deep_dive_strategy,
                    c.implications,
                    c.published_at,
                    co.ticker,
                    f.filing_type,
                    f.fiscal_year,
                    f.fiscal_quarter,
                    f.filing_date,
                    co.name as company_name
                FROM content c
                JOIN filings f ON c.filing_id = f.id
                JOIN companies co ON f.company_id = co.id
                WHERE c.id = %s
            """, (content_id,))

            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise FetchError(f"Content {content_id} not found")

            # Extract data from JSONB key_takeaways
            key_takeaways = row[1] if isinstance(row[1], dict) else {}

            # Convert fiscal_quarter to fiscal_period format
            fiscal_quarter = row[10]
            fiscal_period = f'Q{fiscal_quarter}' if fiscal_quarter else 'FY'

            return {
                'executive_summary': row[0],
                'tldr_headline': key_takeaways.get('headline', ''),
                'tldr_summary': row[0][:500] if row[0] else '',  # First 500 chars
                'tldr_key_points': key_takeaways.get('points', []),
                'deep_headline': key_takeaways.get('headline', ''),
                'deep_intro': row[0],  # executive_summary
                'deep_sections': [],  # Parsed from deep_dive_strategy
                'deep_conclusion': row[5],  # implications
                'key_metrics': key_takeaways.get('metrics', {}),
                'sentiment_score': key_takeaways.get('sentiment'),
                'risk_factors': row[3].split('\n\n') if row[3] else [],
                'opportunities': row[2].split('\n\n') if row[2] else [],
                'deep_dive_strategy': row[4],
                'published_at': row[6],
                'ticker': row[7],
                'filing_type': row[8],
                'fiscal_year': row[9],
                'fiscal_period': fiscal_period,
                'filing_date': row[11],
                'company_name': row[12]
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
        sentiment = content.get('sentiment_score') or 0
        sentiment_class = 'positive' if sentiment > 0.5 else 'negative' if sentiment < -0.2 else 'neutral'
        sentiment_text = 'Positive' if sentiment > 0.5 else 'Negative' if sentiment < -0.2 else 'Neutral'

        # Calculate reading time based on all content
        total_words = (
            len(content.get('deep_intro', '').split()) +
            len(content.get('deep_conclusion', '').split()) +
            sum(len(section.get('content', '').split()) for section in sections if isinstance(section, dict))
        )
        reading_time = max(1, total_words // 200)  # 200 words per minute, minimum 1 min

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
        <nav class="breadcrumb">
            <a href="/" class="breadcrumb-link">
                <img src="/logo.png" alt="10KAY" class="breadcrumb-logo" />
                ← Home
            </a>
        </nav>

        <header class="post-header">
            <div class="meta-info">
                <a href="/{content['ticker'].lower()}" class="ticker ticker-link">{content['ticker']}</a>
                <span class="separator">•</span>
                <span class="filing-type">{content['filing_type']}</span>
                <span class="separator">•</span>
                <span class="fiscal-period">{content['fiscal_period']} {content['fiscal_year']}</span>
                <span class="separator">•</span>
                <span class="sentiment sentiment-{sentiment_class}">{sentiment_text}</span>
            </div>

            <h1 class="headline">{content['deep_headline']}</h1>

            <div class="post-meta">
                <time datetime="{content['filing_date'].isoformat() if content.get('filing_date') else ''}" class="publish-date">
                    {content['filing_date'].strftime('%B %d, %Y') if content.get('filing_date') else ''}
                </time>
                <span class="separator">•</span>
                <span class="reading-time">{reading_time} min read</span>
            </div>
        </header>

        <!-- TLDR Section -->
        <aside class="tldr-box">
            <h2 class="tldr-title">TL;DR</h2>
            <p class="tldr-summary">{content['tldr_summary']}</p>
            <ul class="tldr-points">
                {''.join(f'<li><strong>{point["title"]}</strong>: {point["description"]}</li>' if isinstance(point, dict) else f'<li>{point}</li>' for point in content['tldr_key_points'])}
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

        @media (min-width: 1024px) {
            body {
                padding: 3rem 4rem;
            }
        }

        @media (min-width: 1920px) {
            body {
                padding: 3rem 6rem;
            }
        }

        .blog-post {
            max-width: 1400px;
            margin: 0 auto;
        }

        .breadcrumb {
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #e5e7eb;
        }

        .breadcrumb-link {
            color: #6b7280;
            text-decoration: none;
            font-size: 0.875rem;
            font-weight: 500;
            transition: color 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .breadcrumb-link:hover {
            color: #111827;
        }

        .breadcrumb-logo {
            width: 20px;
            height: 20px;
            display: inline-block;
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

        .ticker-link {
            text-decoration: none;
            transition: color 0.2s ease;
        }

        .ticker-link:hover {
            color: #0052a3;
            text-decoration: underline;
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
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin: 2rem 0;
        }

        .metric-card {
            background: #fff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 1.5rem;
            transition: box-shadow 0.2s ease;
        }

        .metric-card:hover {
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }

        .metric-label {
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b7280;
            margin-bottom: 0.75rem;
            font-weight: 600;
        }

        .metric-value {
            font-size: 1.25rem;
            font-weight: 600;
            color: #111827;
            line-height: 1.2;
            margin-bottom: 0.5rem;
        }

        .metric-change {
            display: flex;
            align-items: center;
            gap: 0.375rem;
            margin-top: 0.5rem;
        }

        .metric-indicator {
            font-size: 1rem;
            font-weight: 600;
        }

        .metric-change-value {
            font-size: 0.875rem;
            font-weight: 600;
        }

        .metric-positive {
            color: #059669;
        }

        .metric-negative {
            color: #dc2626;
        }

        .metric-neutral {
            color: #6b7280;
        }

        .metric-description {
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 0.5rem;
            line-height: 1.5;
        }

        .metric-nested {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #e5e7eb;
        }

        .metric-nested-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
            font-size: 0.875rem;
        }

        .metric-nested-label {
            color: #6b7280;
            font-weight: 500;
        }

        .metric-nested-value {
            font-weight: 600;
            color: #111827;
            display: flex;
            align-items: center;
            gap: 0.375rem;
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

    def _analyze_metric_sentiment(self, value_str: str) -> tuple:
        """
        Analyze a metric value and return (indicator, css_class)
        Returns ('', 'neutral') if no clear direction or if change is too small
        """
        import re

        value_lower = value_str.lower()

        # Extract percentage change if present
        pct_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', value_str)
        if pct_match:
            pct_value = float(pct_match.group(1))
            # Only highlight if >= 5% change
            if pct_value >= 5:
                return ('↑', 'metric-positive')
            elif pct_value <= -5:
                return ('↓', 'metric-negative')
            else:
                return ('', 'metric-neutral')

        # Check for positive keywords
        positive_keywords = ['positive', 'improved', 'growth', 'increased', 'up ', 'gain', 'expansion', 'accelerat']
        negative_keywords = ['negative', 'declined', 'decreased', 'down ', 'loss', 'contraction', 'slowdown', 'deteriorat']

        for keyword in positive_keywords:
            if keyword in value_lower:
                return ('↑', 'metric-positive')

        for keyword in negative_keywords:
            if keyword in value_lower:
                return ('↓', 'metric-negative')

        # Default: no indicator
        return ('', 'metric-neutral')

    def _render_metrics(self, metrics: Dict[str, Any]) -> str:
        """Render key metrics grid with modern card layout"""
        if not metrics:
            return ''

        cards = []
        for label, value in metrics.items():
            # Format label
            label_formatted = label.replace('_', ' ').title()

            # Handle nested dicts (like growth_indicators)
            if isinstance(value, dict):
                # Get first item as main metric, rest as nested
                items = list(value.items())
                if items:
                    main_label, main_value = items[0]
                    main_label_formatted = main_label.replace('_', ' ').title()
                    indicator, css_class = self._analyze_metric_sentiment(str(main_value))

                    # Extract percentage for change display
                    pct_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', str(main_value))
                    change_html = ''
                    if indicator and pct_match:
                        pct_value = pct_match.group(1)
                        change_html = f'''
                        <div class="metric-change">
                            <span class="metric-indicator {css_class}">{indicator}</span>
                            <span class="metric-change-value {css_class}">{pct_value}%</span>
                        </div>
                        '''

                    # Build nested items
                    nested_html = ''
                    if len(items) > 1:
                        nested_html = '<div class="metric-nested">'
                        for sub_label, sub_value in items[1:]:
                            sub_label_formatted = sub_label.replace('_', ' ').title()
                            sub_indicator, sub_css_class = self._analyze_metric_sentiment(str(sub_value))
                            sub_indicator_html = f'<span class="metric-indicator {sub_css_class}">{sub_indicator}</span>' if sub_indicator else ''
                            nested_html += f'''
                            <div class="metric-nested-item">
                                <span class="metric-nested-label">{sub_label_formatted}</span>
                                <span class="metric-nested-value">{sub_indicator_html}{sub_value}</span>
                            </div>
                            '''
                        nested_html += '</div>'

                    # Remove percentage from main value display if it's in change
                    main_value_display = str(main_value)
                    if pct_match:
                        main_value_display = re.sub(r'\s*[+-]?\d+(?:\.\d+)?%', '', main_value_display).strip()

                    cards.append(f"""
                        <div class="metric-card">
                            <div class="metric-label">{label_formatted}</div>
                            <div class="metric-value">{main_value_display}</div>
                            {change_html}
                            {nested_html}
                        </div>
                    """)
            else:
                value_str = str(value)
                indicator, css_class = self._analyze_metric_sentiment(value_str)

                # Extract percentage for change display
                pct_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', value_str)
                change_html = ''
                if indicator and pct_match:
                    pct_value = pct_match.group(1)
                    change_html = f'''
                    <div class="metric-change">
                        <span class="metric-indicator {css_class}">{indicator}</span>
                        <span class="metric-change-value {css_class}">{pct_value}%</span>
                    </div>
                    '''
                    # Remove percentage from main value display
                    value_str = re.sub(r'\s*[+-]?\d+(?:\.\d+)?%', '', value_str).strip()

                cards.append(f"""
                    <div class="metric-card">
                        <div class="metric-label">{label_formatted}</div>
                        <div class="metric-value">{value_str}</div>
                        {change_html}
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
                    published_at = COALESCE(published_at, NOW()),
                    updated_at = NOW()
                WHERE id = %s
            """, (
                generated.output,
                content_id
            ))

            self.db_connection.commit()
            cursor.close()

            if self.logger:
                self.logger.info(
                    f"Saved blog HTML to database and marked as published",
                    extra={'content_id': content_id}
                )

        except Exception as e:
            self.db_connection.rollback()
            raise DatabaseError(f"Failed to save blog HTML: {e}")

    def count_pending_generations(self) -> int:
        """
        Count the number of contents pending generation

        Returns:
            Number of content records with status='analyzed'

        Raises:
            DatabaseError: If database query fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()
            # Content is pending generation if it has no HTML yet (blog_html or email_html is NULL)
            cursor.execute("SELECT COUNT(*) FROM content WHERE blog_html IS NULL OR email_html IS NULL")
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        except Exception as e:
            raise DatabaseError(f"Failed to count pending generations: {e}")

    def get_pending_generations(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get pending content generations from database

        Args:
            limit: Maximum number of items to return (None = all)

        Returns:
            List of content dictionaries with keys: content_id, filing_id, ticker, filing_type

        Raises:
            DatabaseError: If database query fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            query = """
                SELECT c.id as content_id, f.id as filing_id, co.ticker, f.filing_type
                FROM content c
                JOIN filings f ON c.filing_id = f.id
                JOIN companies co ON f.company_id = co.id
                WHERE c.blog_html IS NULL OR c.email_html IS NULL
                ORDER BY c.created_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            columns = ['content_id', 'filing_id', 'ticker', 'filing_type']
            items = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.close()

            return items
        except Exception as e:
            raise DatabaseError(f"Failed to get pending generations: {e}")

    def generate_batch(self, limit: Optional[int] = None, formats: List[str] = None, workers: int = 3) -> Dict[str, int]:
        """
        Generate content for a batch of pending items

        Args:
            limit: Maximum number of items to generate (None = all pending)
            formats: List of formats to generate ('blog', 'email', etc.)
            workers: Number of parallel workers (currently not used, for future parallelization)

        Returns:
            Dictionary with keys 'generated' and 'failed'

        Raises:
            DatabaseError: If database connection fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        if formats is None:
            formats = [ContentFormat.BLOG_POST_HTML]

        # Filter to only supported formats (currently only BLOG_POST_HTML is implemented)
        supported_formats = [fmt for fmt in formats if fmt == ContentFormat.BLOG_POST_HTML]
        if not supported_formats:
            print("Warning: No supported formats requested. Will generate BLOG_POST_HTML by default.")
            supported_formats = [ContentFormat.BLOG_POST_HTML]

        items = self.get_pending_generations(limit=limit)
        generated_count = 0
        failed_count = 0

        for idx, item in enumerate(items, 1):
            try:
                # Generate each format for this content
                for fmt in supported_formats:
                    generated_content = self.generate(item['content_id'], format=fmt)
                    # Save the generated content to the database
                    self.save_generated_content(item['content_id'], generated_content)

                generated_count += 1
                print(f"  [{idx}/{len(items)}] ✓ {item['ticker']} ({item['filing_type']}) generated successfully")
            except Exception as e:
                failed_count += 1
                error_msg = str(e)[:200]  # Truncate long errors
                print(f"  [{idx}/{len(items)}] ✗ {item['ticker']} ({item['filing_type']}) - {error_msg}")
                if self.logger:
                    self.logger.error(f"Failed to generate {item['ticker']}: {e}")

        return {'generated': generated_count, 'failed': failed_count}

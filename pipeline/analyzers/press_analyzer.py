"""
Press Coverage Analyzer

Uses Claude AI to analyze press articles for sentiment and relevance to SEC filings.
Provides sentiment scoring (-1 to 1) and relevance scoring (0 to 1).
"""
import json
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from utils import PipelineLogger


class PressAnalyzer:
    """
    Analyzes press articles using Claude via AWS Bedrock

    Extracts:
    - Sentiment score: -1.0 (very bearish) to 1.0 (very bullish)
    - Relevance score: 0.0 (unrelated) to 1.0 (directly about filing)
    """

    def __init__(self, config, db_connection=None, logger: Optional[PipelineLogger] = None):
        """
        Initialize press analyzer

        Args:
            config: PipelineConfig instance with AWS Bedrock settings
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

        # AWS Bedrock client
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=config.aws.region
        )

        # Model configuration
        self.model_id = getattr(
            config.aws,
            'bedrock_model_id',
            'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
        )
        self.max_tokens = 2048
        self.temperature = 0.3  # Lower for more consistent scoring

        if self.logger:
            self.logger.info(f"Initialized PressAnalyzer with model {self.model_id}")

    def analyze_article(
        self,
        headline: str,
        snippet: str,
        ticker: str,
        company_name: Optional[str] = None,
        filing_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single article for sentiment and relevance

        Args:
            headline: Article headline
            snippet: Article summary/snippet
            ticker: Company ticker symbol
            company_name: Optional company name
            filing_type: Optional filing type (10-K, 10-Q)

        Returns:
            Dictionary with:
                - sentiment_score: float (-1.0 to 1.0)
                - relevance_score: float (0.0 to 1.0)
                - explanation: str (brief reasoning)
        """
        # Build context about the filing
        context = f"Company: {ticker}"
        if company_name:
            context += f" ({company_name})"
        if filing_type:
            context += f"\nFiling type: {filing_type}"

        # Create Claude prompt
        prompt = f"""Analyze this financial press article about {ticker} that was published shortly after their SEC filing.

{context}

Article Headline: {headline}

Article Summary: {snippet}

Please provide:
1. **Sentiment Score** (-1.0 to 1.0):
   - -1.0 = Very bearish (extremely negative about company prospects)
   - -0.5 = Moderately bearish (concerns about performance or outlook)
   - 0.0 = Neutral (balanced or factual reporting)
   - +0.5 = Moderately bullish (positive indicators or optimism)
   - +1.0 = Very bullish (extremely positive about company prospects)

2. **Relevance Score** (0.0 to 1.0):
   - 0.0 = Not related to the filing or company
   - 0.3 = Mentions company but not focused on filing
   - 0.6 = Discusses filing results or related topics
   - 0.9 = Directly analyzes the SEC filing content
   - 1.0 = Comprehensive analysis of the specific filing

3. **Brief Explanation** (1-2 sentences): Why you assigned these scores.

Respond ONLY with valid JSON in this exact format:
{{
  "sentiment_score": 0.0,
  "relevance_score": 0.0,
  "explanation": "Brief reasoning here"
}}"""

        try:
            # Call Claude via Bedrock
            response = self._call_claude(prompt)

            # Parse JSON response
            result = json.loads(response)

            # Validate scores are in expected ranges
            sentiment = float(result.get('sentiment_score', 0.0))
            relevance = float(result.get('relevance_score', 0.0))

            sentiment = max(-1.0, min(1.0, sentiment))  # Clamp to [-1, 1]
            relevance = max(0.0, min(1.0, relevance))  # Clamp to [0, 1]

            return {
                'sentiment_score': sentiment,
                'relevance_score': relevance,
                'explanation': result.get('explanation', '')
            }

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to analyze article: {headline[:50]}...", exception=e)

            # Return neutral scores on error
            return {
                'sentiment_score': 0.0,
                'relevance_score': 0.5,
                'explanation': f'Analysis failed: {str(e)}'
            }

    def analyze_batch(
        self,
        articles: List[Dict[str, Any]],
        ticker: str,
        company_name: Optional[str] = None,
        filing_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple articles in batch

        Args:
            articles: List of dicts with 'headline', 'snippet', 'article_id'
            ticker: Company ticker
            company_name: Optional company name
            filing_type: Optional filing type

        Returns:
            List of analysis results with article_id mapping
        """
        if self.logger:
            self.logger.info(f"Analyzing {len(articles)} articles for {ticker}")

        results = []

        for article in articles:
            try:
                analysis = self.analyze_article(
                    headline=article.get('headline', ''),
                    snippet=article.get('snippet', ''),
                    ticker=ticker,
                    company_name=company_name,
                    filing_type=filing_type
                )

                results.append({
                    'article_id': article.get('article_id'),
                    **analysis
                })

                # Small delay to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to analyze article {article.get('article_id')}",
                        exception=e
                    )
                # Continue with other articles
                continue

        if self.logger:
            self.logger.info(f"Completed analysis of {len(results)}/{len(articles)} articles")

        return results

    def update_article_scores(self, article_id: str, sentiment: float, relevance: float) -> bool:
        """
        Update sentiment and relevance scores in database

        Args:
            article_id: UUID of article in press_coverage table
            sentiment: Sentiment score (-1 to 1)
            relevance: Relevance score (0 to 1)

        Returns:
            True if update successful, False otherwise
        """
        if not self.db_connection:
            raise PressAnalysisError("No database connection available")

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(
                """
                UPDATE press_coverage
                SET sentiment_score = %s, relevance_score = %s
                WHERE id = %s
                """,
                (sentiment, relevance, article_id)
            )
            self.db_connection.commit()
            cursor.close()

            return True

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to update scores for article {article_id}", exception=e)
            return False

    def process_filing_articles(self, filing_id: str) -> int:
        """
        Analyze all articles for a filing and update database

        Args:
            filing_id: UUID of filing in database

        Returns:
            Number of articles analyzed
        """
        if not self.db_connection:
            raise PressAnalysisError("No database connection available")

        # Fetch filing details
        cursor = self.db_connection.cursor()
        cursor.execute(
            """
            SELECT f.id, f.ticker, f.filing_type, c.name
            FROM filings f
            JOIN companies c ON f.company_id = c.id
            WHERE f.id = %s
            """,
            (filing_id,)
        )

        filing_row = cursor.fetchone()
        if not filing_row:
            raise PressAnalysisError(f"Filing not found: {filing_id}")

        filing_id, ticker, filing_type, company_name = filing_row

        # Fetch unanalyzed articles (where sentiment_score IS NULL)
        cursor.execute(
            """
            SELECT id, headline, article_snippet
            FROM press_coverage
            WHERE filing_id = %s AND sentiment_score IS NULL
            """,
            (filing_id,)
        )

        articles_data = []
        for row in cursor.fetchall():
            articles_data.append({
                'article_id': row[0],
                'headline': row[1],
                'snippet': row[2] or ''
            })

        cursor.close()

        if not articles_data:
            if self.logger:
                self.logger.info(f"No unanalyzed articles for filing {filing_id}")
            return 0

        # Analyze articles
        results = self.analyze_batch(
            articles_data,
            ticker=ticker,
            company_name=company_name,
            filing_type=filing_type
        )

        # Update database
        updated = 0
        for result in results:
            if self.update_article_scores(
                article_id=result['article_id'],
                sentiment=result['sentiment_score'],
                relevance=result['relevance_score']
            ):
                updated += 1

        if self.logger:
            self.logger.info(
                f"Updated scores for {updated}/{len(articles_data)} articles"
            )

        return updated

    def _call_claude(self, prompt: str) -> str:
        """
        Call Claude via AWS Bedrock

        Args:
            prompt: The prompt to send to Claude

        Returns:
            Claude's text response

        Raises:
            PressAnalysisError: If API call fails
        """
        # Prepare request for Bedrock (Messages API format)
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())

            # Extract text from response
            if 'content' in response_body and len(response_body['content']) > 0:
                return response_body['content'][0]['text']
            else:
                raise PressAnalysisError("No content in Claude response")

        except ClientError as e:
            raise PressAnalysisError(f"Bedrock API error: {e}")
        except Exception as e:
            raise PressAnalysisError(f"Failed to call Claude: {e}")


class PressAnalysisError(Exception):
    """Raised when press analysis fails"""
    pass

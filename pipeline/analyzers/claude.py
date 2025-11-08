"""
Claude AI analyzer implementation

Analyzes SEC filings using Claude 3.5 Sonnet via AWS Bedrock.
"""
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
import re

from .base import (
    BaseAnalyzer,
    AnalysisResult,
    AnalysisType,
    AnalysisError,
    FetchError,
    DatabaseError
)


class ClaudeAnalyzer(BaseAnalyzer):
    """
    Concrete implementation of Claude AI analyzer

    Uses AWS Bedrock to analyze SEC filings with Claude 3.5 Sonnet.
    Generates both TLDR (free tier) and deep analysis (paid tier).
    """

    def __init__(self, config, db_connection=None, logger=None):
        """Initialize Claude analyzer with AWS Bedrock client"""
        super().__init__(config, db_connection, logger)

        # Initialize Bedrock client
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key
        )

        # Initialize S3 client for fetching filings
        self.s3_client = boto3.client(
            's3',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key
        )

        self.model_id = config.aws.bedrock_model_id

        if self.logger:
            self.logger.info(
                f"Initialized ClaudeAnalyzer",
                extra={'model_id': self.model_id}
            )

    def fetch_filing_content(self, filing_id: str) -> str:
        """
        Fetch filing content from S3

        Args:
            filing_id: Database ID of filing

        Returns:
            Raw filing text content

        Raises:
            FetchError: If fetching fails
        """
        if not self.db_connection:
            raise FetchError("No database connection available")

        try:
            # Get filing S3 URL from database
            cursor = self.db_connection.cursor()
            cursor.execute(
                "SELECT s3_url, html_s3_url FROM filings WHERE id = %s",
                (filing_id,)
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise FetchError(f"Filing {filing_id} not found")

            s3_url = row[0] or row[1]  # Try s3_url first, fall back to html_s3_url

            if not s3_url:
                raise FetchError(f"No S3 URL found for filing {filing_id}")

            # Parse S3 URL (s3://bucket/key)
            if not s3_url.startswith('s3://'):
                raise FetchError(f"Invalid S3 URL: {s3_url}")

            parts = s3_url[5:].split('/', 1)
            bucket = parts[0]
            key = parts[1]

            # Download from S3
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')

            if self.logger:
                self.logger.debug(
                    f"Fetched {len(content)} chars from S3",
                    extra={'filing_id': filing_id}
                )

            return content

        except ClientError as e:
            raise FetchError(f"Failed to fetch from S3: {e}")
        except Exception as e:
            raise FetchError(f"Failed to fetch filing content: {e}")

    def extract_relevant_sections(self, content: str) -> Dict[str, str]:
        """
        Extract relevant sections from SEC filing

        Args:
            content: Raw filing HTML/text

        Returns:
            Dictionary of section names to content

        Common 10-K sections:
        - Item 1: Business
        - Item 1A: Risk Factors
        - Item 7: MD&A
        - Item 8: Financial Statements

        Common 10-Q sections:
        - Part I, Item 1: Financial Statements
        - Part I, Item 2: MD&A
        - Part II, Item 1A: Risk Factors
        """
        sections = {}

        # Remove HTML tags for cleaner text
        text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Extract key sections using regex patterns
        # These patterns match common SEC filing section headers

        # Business section (Item 1)
        business_match = re.search(
            r'(?:ITEM\s+1[^A\d]|Item\s+1[^A\d])(.{0,50}?)(?:BUSINESS|Business)(.*?)(?:ITEM\s+1A|Item\s+1A|ITEM\s+2|Item\s+2)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if business_match:
            sections['business'] = business_match.group(2)[:10000]  # Limit to 10k chars

        # Risk Factors (Item 1A)
        risk_match = re.search(
            r'(?:ITEM\s+1A|Item\s+1A)(.{0,50}?)(?:RISK FACTORS|Risk Factors)(.*?)(?:ITEM\s+1B|Item\s+1B|ITEM\s+2|Item\s+2)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if risk_match:
            sections['risk_factors'] = risk_match.group(2)[:15000]  # Limit to 15k chars

        # MD&A (Item 7 or Part I Item 2)
        mda_match = re.search(
            r'(?:ITEM\s+7|Item\s+7|ITEM\s+2|Item\s+2)(.{0,100}?)(?:MANAGEMENT.?S DISCUSSION AND ANALYSIS|Management.?s Discussion and Analysis)(.*?)(?:ITEM\s+7A|Item\s+7A|ITEM\s+8|Item\s+8|ITEM\s+3|Item\s+3)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if mda_match:
            sections['md_and_a'] = mda_match.group(2)[:20000]  # Limit to 20k chars

        # Financial Statements (Item 8 or Part I Item 1)
        financial_match = re.search(
            r'(?:ITEM\s+8|Item\s+8|ITEM\s+1[^A\d]|Item\s+1[^A\d])(.{0,100}?)(?:FINANCIAL STATEMENTS|Financial Statements)(.*?)(?:ITEM\s+9|Item\s+9|ITEM\s+2|Item\s+2)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if financial_match:
            sections['financial_statements'] = financial_match.group(2)[:15000]  # Limit to 15k chars

        # If we didn't find specific sections, just take the first large chunk
        if not sections:
            sections['full_text'] = text[:30000]

        if self.logger:
            self.logger.debug(f"Extracted {len(sections)} sections")

        return sections

    def _build_analysis_prompt(
        self,
        filing_metadata: Dict[str, Any],
        sections: Dict[str, str],
        analysis_type: AnalysisType
    ) -> str:
        """Build prompt for Claude based on analysis type"""

        company_name = filing_metadata.get('company_name', filing_metadata['ticker'])
        filing_type = filing_metadata['filing_type']
        fiscal_period = filing_metadata['fiscal_period']

        if analysis_type == AnalysisType.QUICK_SUMMARY:
            # TLDR prompt (free tier)
            prompt = f"""Analyze this {filing_type} filing for {company_name} ({fiscal_period}) and provide a concise summary for tech-savvy operators.

**Context:**
- Company: {company_name} ({filing_metadata['ticker']})
- Filing: {filing_type} for {fiscal_period} {filing_metadata['fiscal_year']}
- Filing Date: {filing_metadata['filing_date']}

**Filing Sections:**
{self._format_sections_for_prompt(sections)}

**Task:**
Generate a TLDR summary in JSON format with the following structure:
{{
  "headline": "Attention-grabbing one-line summary (8-12 words)",
  "summary": "2-3 sentence overview highlighting the most important findings",
  "key_points": ["Bullet point 1", "Bullet point 2", "Bullet point 3"],
  "sentiment_score": 0.5,  // -1 (very negative) to 1 (very positive)
  "key_metrics": {{
    "revenue": "value with context",
    "growth_rate": "value with context",
    // other important metrics
  }}
}}

**Style Guide:**
- Tone: Bloomberg Terminal meets The Diff (Byrne Hobart) - direct, analytical, no fluff
- Audience: Tech operators, founders, investors who read fast
- Focus: What matters for decision-making, not what's legally required
- Avoid: Corporate speak, obvious statements, generic analysis

Respond with only valid JSON, no additional text."""

        else:
            # Deep analysis prompt (paid tier)
            prompt = f"""Perform a comprehensive analysis of this {filing_type} filing for {company_name} ({fiscal_period}).

**Context:**
- Company: {company_name} ({filing_metadata['ticker']})
- Filing: {filing_type} for {fiscal_period} {filing_metadata['fiscal_year']}
- Filing Date: {filing_metadata['filing_date']}

**Filing Sections:**
{self._format_sections_for_prompt(sections)}

**Task:**
Generate a deep analysis in JSON format:
{{
  "headline": "Compelling headline (8-15 words)",
  "intro": "2-3 paragraph introduction setting up the key themes",
  "sections": [
    {{
      "title": "Section Title",
      "content": "2-4 paragraphs of analysis with specific details and implications"
    }},
    // 4-6 sections covering: financial performance, strategic moves, risks, opportunities, market position
  ],
  "conclusion": "2-3 paragraphs synthesizing insights and forward-looking implications",
  "key_metrics": {{
    "revenue": "detailed metrics with YoY comparisons",
    "margins": "...",
    "growth_indicators": "...",
    // comprehensive financial snapshot
  }},
  "sentiment_score": 0.5,
  "risk_factors": ["Top risk 1", "Top risk 2", "Top risk 3"],
  "opportunities": ["Key opportunity 1", "Key opportunity 2", "Key opportunity 3"]
}}

**Analysis Framework:**
1. **What Changed**: YoY/QoQ comparisons, inflection points
2. **Why It Matters**: Strategic implications, competitive dynamics
3. **What's Next**: Forward-looking indicators, management guidance
4. **The Nuance**: What others might miss, second-order effects

**Style Guide:**
- Tone: Bloomberg Terminal meets TBPN - authoritative, insightful, opinionated
- Audience: Sophisticated tech operators who want deep understanding
- Focus: Strategic narrative, not just numbers
- Include: Specific figures, direct quotes, concrete examples
- Avoid: Hedging language, surface-level observations

Respond with only valid JSON, no additional text."""

        return prompt

    def _format_sections_for_prompt(self, sections: Dict[str, str]) -> str:
        """Format extracted sections for inclusion in prompt"""
        formatted = []
        for section_name, content in sections.items():
            # Clean up whitespace
            content = re.sub(r'\s+', ' ', content).strip()
            formatted.append(f"### {section_name.replace('_', ' ').title()}\n{content[:5000]}")  # Limit each section
        return "\n\n".join(formatted)

    def _call_bedrock(self, prompt: str) -> Dict[str, Any]:
        """
        Call AWS Bedrock with Claude model

        Args:
            prompt: Prompt text

        Returns:
            Response from Claude

        Raises:
            AnalysisError: If API call fails
        """
        start_time = time.time()

        try:
            # Build request body for Claude 3.5 Sonnet
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.7,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            # Call Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            duration = time.time() - start_time

            # Extract usage stats
            usage = response_body.get('usage', {})
            prompt_tokens = usage.get('input_tokens', 0)
            completion_tokens = usage.get('output_tokens', 0)

            if self.logger:
                self.logger.info(
                    f"Bedrock API call completed",
                    extra={
                        'duration_seconds': round(duration, 2),
                        'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'total_tokens': prompt_tokens + completion_tokens
                    }
                )

            # Extract text from response
            content_blocks = response_body.get('content', [])
            if not content_blocks:
                raise AnalysisError("No content in Bedrock response")

            text = content_blocks[0].get('text', '')

            return {
                'text': text,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'duration': duration
            }

        except ClientError as e:
            raise AnalysisError(f"Bedrock API error: {e}")
        except Exception as e:
            raise AnalysisError(f"Failed to call Bedrock: {e}")

    def analyze_filing(
        self,
        filing_id: str,
        analysis_type: AnalysisType = AnalysisType.DEEP_ANALYSIS
    ) -> AnalysisResult:
        """
        Analyze filing with Claude AI

        Args:
            filing_id: Database ID of filing
            analysis_type: Type of analysis to perform

        Returns:
            AnalysisResult with structured analysis

        Raises:
            AnalysisError: If analysis fails
        """
        if self.logger:
            self.logger.info(
                f"Analyzing filing {filing_id}",
                extra={'filing_id': filing_id, 'analysis_type': analysis_type.value}
            )

        try:
            # Get filing metadata
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT f.ticker, f.filing_type, f.fiscal_year, f.fiscal_period,
                       f.filing_date, c.name as company_name
                FROM filings f
                JOIN companies c ON f.ticker = c.ticker
                WHERE f.id = %s
            """, (filing_id,))

            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise AnalysisError(f"Filing {filing_id} not found")

            filing_metadata = {
                'ticker': row[0],
                'filing_type': row[1],
                'fiscal_year': row[2],
                'fiscal_period': row[3],
                'filing_date': row[4].isoformat(),
                'company_name': row[5]
            }

            # Fetch filing content
            content = self.fetch_filing_content(filing_id)

            # Extract relevant sections
            sections = self.extract_relevant_sections(content)

            # Build prompt
            prompt = self._build_analysis_prompt(filing_metadata, sections, analysis_type)

            # Call Claude
            response = self._call_bedrock(prompt)

            # Parse JSON response
            try:
                analysis_data = json.loads(response['text'])
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response['text'], re.DOTALL)
                if json_match:
                    analysis_data = json.loads(json_match.group(1))
                else:
                    raise AnalysisError("Failed to parse JSON response from Claude")

            # Build AnalysisResult
            if analysis_type == AnalysisType.QUICK_SUMMARY:
                result = AnalysisResult(
                    filing_id=filing_id,
                    tldr_headline=analysis_data['headline'],
                    tldr_summary=analysis_data['summary'],
                    tldr_key_points=analysis_data['key_points'],
                    key_metrics=analysis_data.get('key_metrics'),
                    sentiment_score=analysis_data.get('sentiment_score'),
                    model_version=self.model_id,
                    prompt_tokens=response['prompt_tokens'],
                    completion_tokens=response['completion_tokens'],
                    analysis_duration_seconds=response['duration']
                )
            else:
                # Deep analysis includes both TLDR and deep content
                result = AnalysisResult(
                    filing_id=filing_id,
                    # TLDR (for free tier users)
                    tldr_headline=analysis_data['headline'],
                    tldr_summary=analysis_data['intro'][:500],  # First 500 chars of intro
                    tldr_key_points=[s['title'] for s in analysis_data['sections'][:3]],
                    # Deep analysis (for paid tier)
                    deep_headline=analysis_data['headline'],
                    deep_intro=analysis_data['intro'],
                    deep_sections=analysis_data['sections'],
                    deep_conclusion=analysis_data['conclusion'],
                    key_metrics=analysis_data.get('key_metrics'),
                    sentiment_score=analysis_data.get('sentiment_score'),
                    risk_factors=analysis_data.get('risk_factors'),
                    opportunities=analysis_data.get('opportunities'),
                    model_version=self.model_id,
                    prompt_tokens=response['prompt_tokens'],
                    completion_tokens=response['completion_tokens'],
                    analysis_duration_seconds=response['duration']
                )

            if self.logger:
                self.logger.info(
                    f"Analysis complete",
                    extra={
                        'filing_id': filing_id,
                        'tokens': response['prompt_tokens'] + response['completion_tokens']
                    }
                )

            return result

        except Exception as e:
            if self.logger:
                self.logger.error(f"Analysis failed", exception=e, extra={'filing_id': filing_id})
            raise AnalysisError(f"Failed to analyze filing: {e}")

    def save_to_database(
        self,
        result: AnalysisResult,
        status: str = 'published'
    ) -> str:
        """
        Save analysis result to database

        Args:
            result: AnalysisResult to save
            status: Content status

        Returns:
            Database ID (UUID) of created content record

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            # Insert content record
            cursor.execute("""
                INSERT INTO content (
                    filing_id,
                    status,
                    tldr_headline,
                    tldr_summary,
                    tldr_key_points,
                    deep_headline,
                    deep_intro,
                    deep_sections,
                    deep_conclusion,
                    key_metrics,
                    sentiment_score,
                    risk_factors,
                    opportunities,
                    ai_model_version,
                    ai_prompt_tokens,
                    ai_completion_tokens,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                result.filing_id,
                status,
                result.tldr_headline,
                result.tldr_summary,
                result.tldr_key_points,
                result.deep_headline,
                result.deep_intro,
                json.dumps(result.deep_sections) if result.deep_sections else None,
                result.deep_conclusion,
                json.dumps(result.key_metrics) if result.key_metrics else None,
                result.sentiment_score,
                result.risk_factors,
                result.opportunities,
                result.model_version,
                result.prompt_tokens,
                result.completion_tokens,
                {
                    'analysis_duration_seconds': result.analysis_duration_seconds
                }
            ))

            content_id = cursor.fetchone()[0]

            # Update filing status
            cursor.execute(
                "UPDATE filings SET status = 'analyzed' WHERE id = %s",
                (result.filing_id,)
            )

            self.db_connection.commit()
            cursor.close()

            if self.logger:
                self.logger.info(
                    f"Saved analysis to database",
                    extra={'content_id': content_id, 'filing_id': result.filing_id}
                )

            return content_id

        except Exception as e:
            self.db_connection.rollback()
            raise DatabaseError(f"Failed to save analysis to database: {e}")

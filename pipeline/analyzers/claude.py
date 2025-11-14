"""
Claude AI analyzer implementation

Analyzes SEC filings using Claude Sonnet 4.5 via AWS Bedrock.
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

    Uses AWS Bedrock to analyze SEC filings with Claude Sonnet 4.5.
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
                "SELECT raw_document_url FROM filings WHERE id = %s",
                (filing_id,)
            )

            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise FetchError(f"Filing {filing_id} not found")

            s3_url = row[0]

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
            prompt = f"""Analyze this {filing_type} filing for {company_name} ({fiscal_period}) and provide a substantive summary for tech-savvy operators.

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
  "summary": "4-6 sentence overview providing substantive context. Start with the headline insight, then explain what changed and why it matters. Include 2-3 specific metrics or examples. End with forward-looking implications.",
  "key_points": [
    {{
      "title": "Financial Performance Overview",
      "description": "Full paragraph (4-6 sentences) with headline insight and specific YoY/QoQ numbers. Explain margin trends and growth drivers with basis point changes. Include segment-level details. Discuss sustainability of metrics and changes from prior periods. End with implications for future trajectory."
    }},
    {{
      "title": "Strategic Initiatives and Operational Changes",
      "description": "Full paragraph (4-6 sentences) describing operational or strategic shifts. Explain why management made these changes and competitive implications. Include forward-looking indicators from commentary. Connect strategy to financial performance. Discuss execution risks and timeline."
    }},
    {{
      "title": "Market Position and Competitive Dynamics",
      "description": "Full paragraph (4-6 sentences) analyzing market share trends and positioning. Discuss customer concentration and retention metrics. Explain TAM expansion opportunities. Include competitive threats and advantages. Assess how the company is gaining or losing ground."
    }},
    {{
      "title": "Operational Efficiency and Profitability",
      "description": "Full paragraph (4-6 sentences) explaining operational leverage and cost structure. Discuss efficiency improvements or headwinds. Analyze gross and operating margin trends. Include productivity metrics if available. Assess sustainability of profitability improvements."
    }},
    {{
      "title": "Growth Catalysts and Material Risks",
      "description": "Full paragraph (4-6 sentences) identifying near and medium-term growth drivers. Discuss macro headwinds or tailwinds. Explain key risks material to investment thesis. Assess management's mitigation strategies. Provide forward-looking perspective on key metrics."
    }}
  ],
  "sentiment_score": 0.5,  // -1 (very negative) to 1 (very positive)
  "key_metrics": {{
    "revenue": "value with YoY/QoQ context",
    "growth_rate": "value with trend analysis",
    "margins": "gross and operating with basis point changes",
    // 5-7 other critical metrics with context
  }}
}}

**Style Guide:**
- Tone: Bloomberg Terminal meets The Diff (Byrne Hobart) - direct, analytical, substantive
- Audience: Tech operators, founders, investors who want actionable insights
- Focus: What matters for decision-making, strategic implications, second-order effects
- Include: Specific numbers, comparisons, context, nuance
- Avoid: Corporate speak, obvious statements, generic analysis, vague descriptions

Respond with only valid JSON, no additional text."""

        else:
            # Deep analysis prompt (paid tier)
            prompt = f"""Perform a comprehensive, substantive analysis of this {filing_type} filing for {company_name} ({fiscal_period}). This should be a 5-7 minute read with deep insights.

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
  "tldr": {{
    "summary": "4-6 sentence overview providing substantive context. Start with the headline insight, then explain what changed and why it matters. Include 2-3 specific metrics or examples. End with forward-looking implications.",
    "key_points": [
      {{
        "title": "Financial Performance Overview",
        "description": "Full paragraph (4-6 sentences) with headline insight and specific YoY/QoQ numbers. Explain margin trends and growth drivers with basis point changes. Include segment-level details. Discuss sustainability of metrics and changes from prior periods. End with implications for future trajectory."
      }},
      {{
        "title": "Strategic Initiatives and Operational Changes",
        "description": "Full paragraph (4-6 sentences) describing operational or strategic shifts. Explain why management made these changes and competitive implications. Include forward-looking indicators from commentary. Connect strategy to financial performance. Discuss execution risks and timeline."
      }},
      {{
        "title": "Market Position and Competitive Dynamics",
        "description": "Full paragraph (4-6 sentences) analyzing market share trends and positioning. Discuss customer concentration and retention metrics. Explain TAM expansion opportunities. Include competitive threats and advantages. Assess how the company is gaining or losing ground."
      }},
      {{
        "title": "Operational Efficiency and Profitability",
        "description": "Full paragraph (4-6 sentences) explaining operational leverage and cost structure. Discuss efficiency improvements or headwinds. Analyze gross and operating margin trends. Include productivity metrics if available. Assess sustainability of profitability improvements."
      }},
      {{
        "title": "Growth Catalysts and Material Risks",
        "description": "Full paragraph (4-6 sentences) identifying near and medium-term growth drivers. Discuss macro headwinds or tailwinds. Explain key risks material to investment thesis. Assess management's mitigation strategies. Provide forward-looking perspective on key metrics."
      }}
    ]
  }},
  "intro": "4-6 substantive paragraphs (250-350 words total) setting up the key themes. Start with the headline insight in context. Explain what changed YoY/QoQ with specific numbers. Identify 2-3 major themes. Provide competitive context. End with what this means for the business trajectory.",
  "sections": [
    {{
      "title": "Financial Performance Deep Dive",
      "content": "6-8 paragraphs (400-600 words). Break down revenue by segment with YoY/QoQ trends. Analyze margin expansion/compression with drivers. Discuss cash flow and capital allocation. Compare to peers. Identify inflection points or concerning trends. Include specific numbers, percentages, and basis point changes throughout."
    }},
    {{
      "title": "Strategic Shifts and Product Evolution",
      "content": "6-8 paragraphs (400-600 words). Analyze new product launches, R&D investments, strategic pivots. Discuss go-to-market changes. Examine partnerships and M&A. Connect product strategy to financials. Assess competitive positioning. Include forward-looking indicators from management commentary."
    }},
    {{
      "title": "Market Dynamics and Competitive Position",
      "content": "5-7 paragraphs (350-500 words). Assess market share trends. Analyze competitive threats and advantages. Discuss regulatory environment. Examine customer concentration and churn. Include macroeconomic factors affecting the business."
    }},
    {{
      "title": "Risk Factors and Headwinds",
      "content": "5-7 paragraphs (350-500 words). Deep dive into material risks from filing. Assess likelihood and potential impact. Discuss management's mitigation strategies. Compare to prior periods. Include second-order effects."
    }},
    {{
      "title": "Growth Opportunities and Catalysts",
      "content": "5-7 paragraphs (350-500 words). Identify untapped markets and expansion opportunities. Analyze operational leverage potential. Discuss innovation pipeline. Assess M&A potential. Include TAM analysis where relevant."
    }}
  ],
  "conclusion": "5-6 paragraphs (300-400 words) synthesizing insights and forward-looking implications. Recap the 2-3 most important themes. Assess whether the business is accelerating or decelerating. Identify key metrics to watch in next quarter. Provide actionable takeaways for operators. End with contrarian or non-obvious insight.",
  "key_metrics": {{
    "revenue": "$XXX.XB (±X.X% YoY, ±X.X% QoQ) with segment breakdown and trend analysis",
    "gross_margin": "XX.X% (±XXbps YoY) with drivers explanation",
    "operating_margin": "XX.X% (±XXbps YoY) with efficiency analysis",
    "free_cash_flow": "$XXB (±X% YoY) with conversion rate",
    "growth_indicators": {{
      "customer_count": "details with growth rate",
      "arr_or_bookings": "details with trends",
      "retention_metrics": "details with cohort analysis"
    }},
    // 8-12 critical metrics total with full context
  }},
  "sentiment_score": 0.5,
  "risk_factors": [
    "Specific risk 1 with quantified impact assessment",
    "Specific risk 2 with likelihood and mitigation strategy",
    "Specific risk 3 with industry context",
    "Specific risk 4 if material"
  ],
  "opportunities": [
    "Specific opportunity 1 with TAM/market size context",
    "Specific opportunity 2 with timeline and barriers to entry",
    "Specific opportunity 3 with competitive advantage analysis",
    "Specific opportunity 4 if material"
  ]
}}

**Analysis Framework:**
1. **What Changed**: YoY/QoQ comparisons, inflection points, trend reversals
2. **Why It Matters**: Strategic implications, competitive dynamics, market share shifts
3. **What's Next**: Forward-looking indicators, management guidance, pipeline visibility
4. **The Nuance**: What others might miss, second-order effects, non-obvious correlations
5. **The Contrarian Take**: Challenge conventional wisdom, identify misunderstood aspects

**Style Guide:**
- Tone: Bloomberg Terminal meets Stratechery - authoritative, insightful, opinionated, substantive
- Audience: Sophisticated tech operators, founders, investors who want deep understanding
- Length: Each section should be 350-600 words for a total 5-7 minute read (2000-3000 words)
- Focus: Strategic narrative woven with numbers, not just data dumps
- Include: Specific figures, YoY/QoQ comparisons, segment breakdowns, direct quotes, concrete examples
- Avoid: Hedging language, surface-level observations, obvious points, filler content

**Critical**: This is PAID tier content. Make it substantially deeper and more insightful than a free summary.

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
            # Build request body for Claude Sonnet 4.5
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

            # Debug: Print full response to stderr
            import sys
            print(f"\n=== DEBUG: Full Bedrock Response ===", file=sys.stderr)
            print(f"Response keys: {list(response_body.keys())}", file=sys.stderr)
            print(f"Full response: {response_body}", file=sys.stderr)
            print(f"=== END DEBUG ===\n", file=sys.stderr)

            # Debug: Log full response structure
            if self.logger:
                self.logger.info(
                    f"Full Bedrock response structure",
                    extra={
                        'response_keys': list(response_body.keys()),
                        'response_body_sample': str(response_body)[:500]
                    }
                )

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
                if self.logger:
                    self.logger.error(
                        f"No content blocks in response",
                        extra={'response_body': response_body}
                    )
                raise AnalysisError("No content in Bedrock response")

            text = content_blocks[0].get('text', '')

            if not text:
                if self.logger:
                    self.logger.error(
                        f"Empty text in content block",
                        extra={
                            'content_blocks': content_blocks,
                            'first_block': content_blocks[0] if content_blocks else None
                        }
                    )
                raise AnalysisError("Empty text response from Claude")

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
                SELECT c.ticker, f.filing_type, f.fiscal_year, f.fiscal_quarter,
                       f.filing_date, c.name as company_name
                FROM filings f
                JOIN companies c ON f.company_id = c.id
                WHERE f.id = %s
            """, (filing_id,))

            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise AnalysisError(f"Filing {filing_id} not found")

            # Convert fiscal_quarter back to fiscal_period format
            fiscal_quarter = row[3]
            fiscal_period = f'Q{fiscal_quarter}' if fiscal_quarter else 'FY'

            filing_metadata = {
                'ticker': row[0],
                'filing_type': row[1],
                'fiscal_year': row[2],
                'fiscal_period': fiscal_period,
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
                    try:
                        analysis_data = json.loads(json_match.group(1))
                    except json.JSONDecodeError as e:
                        if self.logger:
                            self.logger.error(
                                f"Failed to parse JSON from markdown code block",
                                extra={
                                    'filing_id': filing_id,
                                    'response_preview': response['text'][:500],
                                    'error': str(e)
                                }
                            )
                        raise AnalysisError(f"Failed to parse JSON response from Claude: {e}")
                else:
                    # Log the actual response for debugging data quality issues
                    if self.logger:
                        self.logger.error(
                            f"Claude returned non-JSON response (possible invalid filing)",
                            extra={
                                'filing_id': filing_id,
                                'company': filing_metadata.get('ticker'),
                                'filing_type': filing_metadata.get('filing_type'),
                                'response': response['text'][:1000]
                            }
                        )
                    raise AnalysisError(f"Failed to parse JSON response from Claude: {response['text'][:200]}")

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
                tldr = analysis_data.get('tldr', {})
                result = AnalysisResult(
                    filing_id=filing_id,
                    # TLDR (for free tier users) - now from dedicated tldr section
                    tldr_headline=analysis_data['headline'],
                    tldr_summary=tldr.get('summary', analysis_data['intro'][:500]),  # Fallback to intro if no tldr
                    tldr_key_points=tldr.get('key_points', [s['title'] for s in analysis_data['sections'][:3]]),  # Fallback to sections
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

            # Get company_id from filing_id
            cursor.execute("SELECT company_id FROM filings WHERE id = %s", (result.filing_id,))
            company_id = cursor.fetchone()[0]

            # Map AnalysisResult to existing content table schema
            # Combine deep analysis sections into text blocks
            deep_dive_strategy = ""
            if result.deep_sections:
                for section in result.deep_sections:
                    deep_dive_strategy += f"## {section['title']}\n\n{section['content']}\n\n"

            # Insert content record
            cursor.execute("""
                INSERT INTO content (
                    filing_id,
                    company_id,
                    executive_summary,
                    key_takeaways,
                    deep_dive_opportunities,
                    deep_dive_risks,
                    deep_dive_strategy,
                    implications
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                result.filing_id,
                company_id,
                result.tldr_summary or result.deep_intro,
                json.dumps({
                    'headline': result.tldr_headline,
                    'points': result.tldr_key_points,
                    'metrics': result.key_metrics,
                    'sentiment': result.sentiment_score,
                    'model': result.model_version,
                    'tokens': (result.prompt_tokens or 0) + (result.completion_tokens or 0),
                    'duration': result.analysis_duration_seconds
                }),
                '\n\n'.join(result.opportunities) if result.opportunities else None,
                '\n\n'.join(result.risk_factors) if result.risk_factors else None,
                deep_dive_strategy if deep_dive_strategy else (result.deep_intro or ''),
                result.deep_conclusion
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

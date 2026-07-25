"""
Claude AI analyzer implementation

Analyzes SEC filings using Claude Sonnet 4.5 via AWS Bedrock.
"""
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
import re
import html

from ..db import (
    ContentRecord,
    ContentRepository,
    DatabaseError as DbError,
    FilingRepository,
    RecordNotFound,
    build_slug,
    transaction,
)
from .base import (
    BaseAnalyzer,
    AnalysisResult,
    AnalysisType,
    AnalysisError,
    FetchError,
    DatabaseError
)
from .synthesis import (
    SynthesisError,
    SynthesisReport,
    extract_json_object,
    normalize_analysis,
)

#: Bedrock error codes worth retrying. Anything else (AccessDenied,
#: ValidationException, ResourceNotFound) will fail identically on retry, so
#: retrying only delays the failure and burns the run's time budget.
RETRYABLE_BEDROCK_ERRORS = {
    'ThrottlingException',
    'TooManyRequestsException',
    'ServiceUnavailableException',
    'InternalServerException',
    'ModelTimeoutException',
    'ModelNotReadyException',
}


def _parse_s3_url(s3_url: str) -> tuple:
    """
    Split ``s3://bucket/key`` into ``(bucket, key)``.

    The old inline version did ``s3_url[5:].split('/', 1)`` and indexed
    ``parts[1]`` unguarded, so a malformed URL raised IndexError instead of
    saying what was wrong with it.
    """
    if not s3_url or not s3_url.startswith('s3://'):
        raise FetchError(f"Not an S3 URL: {s3_url!r}")

    remainder = s3_url[5:]
    bucket, separator, key = remainder.partition('/')
    if not bucket or not separator or not key:
        raise FetchError(f"S3 URL {s3_url!r} is missing a bucket or key")
    return bucket, key


class ClaudeAnalyzer(BaseAnalyzer):
    """
    Concrete implementation of Claude AI analyzer

    Uses AWS Bedrock to analyze SEC filings with Claude Sonnet 4.5.
    Generates both TLDR (free tier) and deep analysis (paid tier).

    Parsing lives in ``synthesis.py`` and persistence in ``pipeline.db``; this
    class is responsible only for talking to S3 and Bedrock and stitching the
    two together.
    """

    def __init__(self, config, db_connection=None, logger=None):
        """Initialize Claude analyzer with AWS Bedrock client"""
        super().__init__(config, db_connection, logger)

        # Bedrock's default read timeout is 60s; a deep analysis routinely runs
        # longer, and a timeout mid-generation is indistinguishable from a hang.
        boto_config = BotoConfig(
            read_timeout=900,
            connect_timeout=30,
            retries={'max_attempts': 0},  # retries are handled in _call_bedrock
        )

        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key,
            config=boto_config,
        )

        # Initialize S3 client for fetching filings
        self.s3_client = boto3.client(
            's3',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key
        )

        self.model_id = config.aws.bedrock_model_id
        self.max_tokens = getattr(config.aws, 'bedrock_max_tokens', 16384)
        self.temperature = getattr(config.aws, 'bedrock_temperature', 0.3)

        # Repositories are resolved from self.db_connection on each use rather
        # than cached here: several backfill scripts reconnect mid-run and
        # reassign `analyzer.db_connection`, which would leave cached
        # repositories bound to a closed connection.

        if self.logger:
            self.logger.info(
                "Initialized ClaudeAnalyzer",
                extra={
                    'model_id': self.model_id,
                    'max_tokens': self.max_tokens,
                    'region': config.aws.region,
                    'bucket': config.aws.s3_filings_bucket,
                },
            )

    def _require_repos(self):
        """
        Build repositories bound to the *current* connection.

        Fails with a clear message rather than an AttributeError on None.
        """
        if self.db_connection is None:
            raise DatabaseError("ClaudeAnalyzer requires a database connection")
        return (
            FilingRepository(self.db_connection),
            ContentRepository(self.db_connection),
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
        filings, _ = self._require_repos()

        try:
            context = filings.get_context(filing_id)
        except RecordNotFound as e:
            raise FetchError(str(e)) from e
        except DbError as e:
            raise FetchError(f"Failed to look up filing {filing_id}: {e}") from e

        s3_url = context.get('raw_document_url')
        if not s3_url:
            raise FetchError(
                f"Filing {filing_id} ({context.get('ticker')}) has no raw_document_url; "
                "the fetch phase did not complete for it"
            )

        bucket, key = _parse_s3_url(s3_url)

        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            raw = response['Body'].read()
        except ClientError as e:
            raise FetchError(f"Failed to fetch {s3_url} from S3: {e}") from e

        # SEC filings are not reliably UTF-8; a stray byte used to abort the
        # whole analysis with a UnicodeDecodeError.
        content = raw.decode('utf-8', errors='replace')

        if not content.strip():
            raise FetchError(f"Filing {filing_id} is empty in S3 at {s3_url}")

        if self.logger:
            self.logger.debug(
                f"Fetched {len(content)} chars from S3",
                extra={'filing_id': filing_id}
            )

        return content

    def _extract_html_tables(self, content: str) -> str:
        """
        Extract and convert HTML tables to readable text format

        Targets financial statement tables in HTML/XBRL filings.
        Handles nested tables, merged cells, and HTML entities.

        Args:
            content: Raw HTML content

        Returns:
            Converted table text with financial data
        """
        tables_text = []

        # Find all table elements
        table_pattern = r'<table[^>]*>(.*?)</table>'
        tables = re.findall(table_pattern, content, re.IGNORECASE | re.DOTALL)

        for table_html in tables:
            # Skip navigation/formatting tables (usually short)
            if len(table_html) < 200:
                continue

            # Extract rows
            row_pattern = r'<tr[^>]*>(.*?)</tr>'
            rows = re.findall(row_pattern, table_html, re.IGNORECASE | re.DOTALL)

            if not rows:
                continue

            table_rows = []
            for row_html in rows:
                # Extract cells (both td and th)
                cell_pattern = r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>'
                cells = re.findall(cell_pattern, row_html, re.IGNORECASE | re.DOTALL)

                if cells:
                    # Clean up cell content
                    cleaned_cells = []
                    for cell in cells:
                        # Remove nested HTML tags
                        cell_text = re.sub(r'<[^>]+>', ' ', cell)
                        # Decode HTML entities
                        cell_text = html.unescape(cell_text)
                        # Remove extra whitespace
                        cell_text = re.sub(r'\s+', ' ', cell_text).strip()
                        if cell_text:
                            cleaned_cells.append(cell_text)

                    if cleaned_cells:
                        table_rows.append(' | '.join(cleaned_cells))

            if table_rows:
                tables_text.append('\n'.join(table_rows))

        return '\n\n'.join(tables_text)

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
        is_html = '<table' in content.lower() or '<html' in content.lower()

        if is_html:
            # For HTML/XBRL filings, extract HTML tables for better financial data
            html_tables = self._extract_html_tables(content)
            if html_tables:
                sections['financial_statements'] = html_tables[:30000]  # Increased limit for table data

            # Also try regex extraction as fallback
            financial_match = re.search(
                r'(?:ITEM\s+8|Item\s+8|ITEM\s+1[^A\d]|Item\s+1[^A\d])(.{0,100}?)(?:FINANCIAL STATEMENTS|Financial Statements)(.*?)(?:ITEM\s+9|Item\s+9|ITEM\s+2|Item\s+2)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if financial_match and 'financial_statements' not in sections:
                sections['financial_statements'] = financial_match.group(2)[:15000]
        else:
            # Plain text filings use standard regex extraction
            financial_match = re.search(
                r'(?:ITEM\s+8|Item\s+8|ITEM\s+1[^A\d]|Item\s+1[^A\d])(.{0,100}?)(?:FINANCIAL STATEMENTS|Financial Statements)(.*?)(?:ITEM\s+9|Item\s+9|ITEM\s+2|Item\s+2)',
                text,
                re.IGNORECASE | re.DOTALL
            )
            if financial_match:
                sections['financial_statements'] = financial_match.group(2)[:15000]

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
  "bull_case": "Concise 15-word maximum summary of the strongest bullish argument from this filing",
  "bear_case": "Concise 15-word maximum summary of the strongest bearish argument or risk from this filing",
  "key_metrics": {{
    "revenue": "value with YoY/QoQ context",
    "net_income": "value with YoY/QoQ context",
    "rd_spend": "value with YoY/QoQ context and as % of revenue",
    "growth_rate": "value with trend analysis",
    "margins": "gross and operating with basis point changes",
    // 4-6 other critical metrics with context
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
    "net_income": "$XXB (±X.X% YoY, ±X.X% QoQ) with margin context",
    "rd_spend": "$XB (±X.X% YoY) and X.X% of revenue with trend analysis",
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
  "bull_case": "Concise 15-word maximum summary of the strongest bullish argument from this filing",
  "bear_case": "Concise 15-word maximum summary of the strongest bearish argument or risk from this filing",
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
        Call AWS Bedrock with the Claude model.

        Returns a dict with ``text``, token counts, ``duration`` and
        ``stop_reason``. ``stop_reason == 'max_tokens'`` is surfaced rather than
        swallowed: it is the signal that the response is truncated, and the
        caller records it as a data-quality flag on the stored analysis.

        Raises:
            AnalysisError: If the API call fails
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        start_time = time.time()
        response = self._invoke_with_retry(request_body)
        duration = time.time() - start_time

        try:
            response_body = json.loads(response['body'].read())
        except (ValueError, KeyError) as e:
            raise AnalysisError(f"Bedrock returned an unreadable envelope: {e}") from e

        usage = response_body.get('usage', {}) or {}
        prompt_tokens = usage.get('input_tokens', 0)
        completion_tokens = usage.get('output_tokens', 0)
        stop_reason = response_body.get('stop_reason')

        content_blocks = response_body.get('content') or []
        text = ''.join(
            block.get('text', '')
            for block in content_blocks
            if isinstance(block, dict) and block.get('type', 'text') == 'text'
        )

        if not text.strip():
            raise AnalysisError(
                "Bedrock returned no text content "
                f"(stop_reason={stop_reason!r}, blocks={len(content_blocks)})"
            )

        if self.logger:
            self.logger.info(
                "Bedrock call completed",
                extra={
                    'duration_seconds': round(duration, 2),
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'stop_reason': stop_reason,
                },
            )
            if stop_reason == 'max_tokens':
                self.logger.warning(
                    "Response hit the max_tokens ceiling and is truncated",
                    extra={'max_tokens': self.max_tokens},
                )

        return {
            'text': text,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'duration': duration,
            'stop_reason': stop_reason,
        }

    def _invoke_with_retry(self, request_body: Dict[str, Any]):
        """
        Invoke the model, retrying only errors that can succeed on retry.

        The previous loop retried every exception three times, including
        AccessDeniedException and ValidationException — turning a
        misconfiguration into a slow failure and, under throttling, into a
        thundering herd because the backoff had no real jitter.
        """
        attempts = max(1, getattr(self.config, 'max_retries', 3))
        base_delay = getattr(self.config, 'retry_delay', 2.0)
        last_error: Optional[BaseException] = None

        for attempt in range(1, attempts + 1):
            try:
                return self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    contentType='application/json',
                    accept='application/json',
                )
            except ClientError as e:
                code = e.response.get('Error', {}).get('Code', '')
                last_error = e
                if code not in RETRYABLE_BEDROCK_ERRORS:
                    raise AnalysisError(f"Bedrock error {code}: {e}") from e
            except Exception as e:  # network-level failures are worth a retry
                last_error = e

            if attempt == attempts:
                break

            # Full jitter: sleep uniformly in [0, base * 2^n]. Without jitter,
            # parallel workers throttled at the same moment retry in lockstep
            # and re-throttle each other.
            import random
            delay = random.uniform(0, base_delay * (2 ** (attempt - 1)))
            if self.logger:
                self.logger.warning(
                    f"Bedrock call failed (attempt {attempt}/{attempts}), "
                    f"retrying in {delay:.1f}s",
                    extra={'error': str(last_error)[:300]},
                )
            time.sleep(delay)

        raise AnalysisError(
            f"Bedrock call failed after {attempts} attempts: {last_error}"
        )

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

        filings, _ = self._require_repos()
        deep = analysis_type != AnalysisType.QUICK_SUMMARY

        # One round trip for everything the prompt and the slug need.
        try:
            context = filings.get_context(filing_id)
        except RecordNotFound as e:
            raise AnalysisError(str(e)) from e
        except DbError as e:
            raise AnalysisError(f"Could not load filing {filing_id}: {e}") from e

        filing_date = context.get('filing_date')
        filing_metadata = {
            'ticker': context['ticker'],
            'filing_type': context['filing_type'],
            'fiscal_year': context['fiscal_year'],
            'fiscal_period': context['fiscal_period'],
            'filing_date': filing_date.isoformat() if filing_date else 'unknown',
            'company_name': context.get('company_name') or context['ticker'],
        }

        content = self.fetch_filing_content(filing_id)
        sections = self.extract_relevant_sections(content)

        if not sections:
            raise AnalysisError(
                f"No usable text extracted from filing {filing_id} "
                f"({filing_metadata['ticker']} {filing_metadata['filing_type']})"
            )

        prompt = self._build_analysis_prompt(filing_metadata, sections, analysis_type)
        response = self._call_bedrock(prompt)

        # Parse and normalize. Both steps raise SynthesisError with the reason
        # and a response preview, instead of a bare JSONDecodeError.
        try:
            data, repaired = extract_json_object(response['text'])
            normalized, report = normalize_analysis(data, deep=deep, repaired=repaired)
        except SynthesisError as e:
            if self.logger:
                self.logger.error(
                    "Could not synthesize a usable analysis from the model response",
                    extra={
                        'filing_id': filing_id,
                        'ticker': filing_metadata['ticker'],
                        'filing_type': filing_metadata['filing_type'],
                        'stop_reason': response.get('stop_reason'),
                        'response_preview': response['text'][:600],
                    },
                )
            raise AnalysisError(f"Synthesis failed for filing {filing_id}: {e}") from e

        if response.get('stop_reason') == 'max_tokens':
            report.warnings.append('response truncated at max_tokens')

        if self.logger and not report.is_clean:
            self.logger.warning(
                "Analysis stored with data-quality flags",
                extra={
                    'filing_id': filing_id,
                    'ticker': filing_metadata['ticker'],
                    **report.to_dict(),
                },
            )

        result = AnalysisResult(
            filing_id=filing_id,
            tldr_headline=normalized['headline'],
            tldr_summary=normalized['summary'],
            tldr_key_points=normalized['key_points'],
            deep_headline=normalized['headline'] if deep else None,
            deep_intro=normalized['intro'] if deep else None,
            deep_sections=normalized['sections'] if deep else None,
            deep_conclusion=normalized['conclusion'] if deep else None,
            key_metrics=normalized['key_metrics'],
            sentiment_score=normalized['sentiment_score'],
            bull_case=normalized['bull_case'],
            bear_case=normalized['bear_case'],
            risk_factors=normalized['risk_factors'],
            opportunities=normalized['opportunities'],
            model_version=self.model_id,
            prompt_tokens=response['prompt_tokens'],
            completion_tokens=response['completion_tokens'],
            analysis_duration_seconds=response['duration'],
        )
        # Carried to save_to_database so the flags land in key_takeaways.
        self._last_report = report

        if self.logger:
            self.logger.info(
                "Analysis complete",
                extra={
                    'filing_id': filing_id,
                    'tokens': response['prompt_tokens'] + response['completion_tokens'],
                    'sections': len(normalized['sections']),
                },
            )

        return result

    def save_to_database(
        self,
        result: AnalysisResult,
        status: str = 'published'
    ) -> str:
        """
        Save an analysis and advance the filing's status, atomically.

        Everything -- the content upsert and the ``filings.status`` update --
        runs in one transaction. Previously the content insert was committed
        before the status update was even issued, so a crash in between left a
        filing marked ``pending`` with content already written, and the next run
        paid Bedrock for it a second time.

        The write is idempotent: re-analyzing a filing updates the existing
        current content row and bumps its version rather than colliding on the
        unique slug.

        Returns:
            Database ID (UUID) of the content record
        """
        filings, contents = self._require_repos()

        try:
            context = filings.get_context(result.filing_id)
        except RecordNotFound as e:
            raise DatabaseError(str(e)) from e

        slug = build_slug(
            context['ticker'],
            context['filing_type'],
            context['fiscal_year'],
            context['fiscal_quarter'],
        )

        # Deep sections are stored as one markdown block in deep_dive_strategy;
        # the original structure is preserved in key_takeaways so renderers can
        # reconstruct headings without re-parsing markdown.
        strategy = ''
        for section in (result.deep_sections or []):
            strategy += f"## {section.get('title', 'Section')}\n\n{section.get('content', '')}\n\n"
        strategy = strategy.strip() or (result.deep_intro or '')

        summary = result.tldr_summary or result.deep_intro
        if not summary:
            raise DatabaseError(
                f"Refusing to save analysis for filing {result.filing_id}: "
                "no summary or intro (content.executive_summary is NOT NULL)"
            )

        report = getattr(self, '_last_report', None)
        key_takeaways = {
            'headline': result.tldr_headline,
            'points': result.tldr_key_points or [],
            'metrics': result.key_metrics or {},
            'sentiment': result.sentiment_score,
            'bull_case': result.bull_case,
            'bear_case': result.bear_case,
            'sections': result.deep_sections or [],
            'conclusion': result.deep_conclusion,
            'model': result.model_version,
            'tokens': (result.prompt_tokens or 0) + (result.completion_tokens or 0),
            'duration': result.analysis_duration_seconds,
            'analyzed_at': datetime.utcnow().isoformat(),
        }
        if report is not None and not report.is_clean:
            key_takeaways['synthesis'] = report.to_dict()

        record = ContentRecord(
            filing_id=result.filing_id,
            company_id=str(context['company_id']),
            slug=slug,
            executive_summary=summary,
            key_takeaways=key_takeaways,
            deep_dive_opportunities=(
                '\n\n'.join(result.opportunities) if result.opportunities else None
            ),
            deep_dive_risks=(
                '\n\n'.join(result.risk_factors) if result.risk_factors else None
            ),
            deep_dive_strategy=strategy or None,
            implications=result.deep_conclusion,
            meta_description=(summary or '')[:300] or None,
        )

        try:
            with transaction(self.db_connection):
                upserted = contents.upsert_analysis(record)
                filings.set_status(result.filing_id, 'analyzed', processed=True)
        except DbError as e:
            raise DatabaseError(
                f"Failed to save analysis for filing {result.filing_id}: {e}"
            ) from e

        if self.logger:
            self.logger.info(
                "Saved analysis to database",
                extra={
                    'content_id': upserted.id,
                    'filing_id': result.filing_id,
                    'slug': record.slug,
                    'created': upserted.created,
                },
            )

        return upserted.id

    def count_pending_filings(self) -> int:
        """
        Count filings pending analysis.

        Delegates to FilingRepository, which also excludes filings that already
        have content -- a filing left at status='pending' after a crash used to
        be counted (and re-analyzed) even though its analysis existed.
        """
        filings, _ = self._require_repos()
        try:
            return filings.count_pending()
        except DbError as e:
            raise DatabaseError(f"Failed to count pending filings: {e}") from e

    def get_pending_filings(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get pending filings.

        ``limit`` is bound as a parameter rather than interpolated into the SQL.
        """
        filings, _ = self._require_repos()
        try:
            return filings.pending(limit=limit)
        except DbError as e:
            raise DatabaseError(f"Failed to get pending filings: {e}") from e

    def analyze_batch(self, limit: Optional[int] = None, workers: int = 3) -> Dict[str, int]:
        """
        Analyze pending filings and persist each result.

        The previous implementation called ``analyze_filing()`` and nothing
        else -- it never called ``save_to_database()``. Every filing was sent to
        Bedrock, charged for, printed as "analyzed successfully", and discarded;
        the filing stayed ``pending`` so the next run did it again. This now goes
        through ``process_filing()``, which analyzes *and* saves.

        Returns counts for analyzed / skipped / failed. ``skipped`` is filings
        that already had content, which is a normal outcome on a rerun and not a
        failure.
        """
        filings = self.get_pending_filings(limit=limit)
        stats = {'analyzed': 0, 'skipped': 0, 'failed': 0, 'total': len(filings)}

        for idx, filing in enumerate(filings, 1):
            label = f"{filing['ticker']} ({filing['filing_type']})"
            try:
                content_id = self.process_filing(
                    filing_id=filing['filing_id'],
                    analysis_type=AnalysisType.DEEP_ANALYSIS,
                    skip_existing=True,
                )
                if content_id:
                    stats['analyzed'] += 1
                    print(f"  [{idx}/{len(filings)}] \u2713 {label} saved as {content_id}")
                else:
                    stats['skipped'] += 1
                    print(f"  [{idx}/{len(filings)}] \u2298 {label} already analyzed")
            except Exception as e:
                stats['failed'] += 1
                print(f"  [{idx}/{len(filings)}] \u2717 {label} - {str(e)[:200]}")
                if self.logger:
                    self.logger.error(
                        f"Failed to analyze {label}",
                        exception=e,
                        extra={'filing_id': filing['filing_id']},
                    )
                # Record why, so a filing does not sit in 'pending' with no trace.
                self._mark_failed(filing['filing_id'], e)

        return stats

    def _mark_failed(self, filing_id: str, error: BaseException) -> None:
        """Best-effort: note the failure on the filing without masking the cause."""
        filings, _ = self._require_repos()
        try:
            filings.set_status(filing_id, 'pending', error_message=str(error)[:1000])
        except DbError:
            if self.logger:
                self.logger.warning(
                    "Could not record failure on filing",
                    extra={'filing_id': filing_id},
                )

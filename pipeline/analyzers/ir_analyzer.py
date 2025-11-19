"""
IR Document Analyzer

Analyzes investor relations documents to extract key takeaways and determine
relevance to associated 10-K/10-Q filings.
"""
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from utils import PipelineLogger


class IRAnalysisResult:
    """Result of analyzing an IR document"""

    def __init__(
        self,
        ir_document_id: str,
        analysis_summary: str,
        relevance_score: float,
        key_topics: List[str],
        salient_takeaways: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.ir_document_id = ir_document_id
        self.analysis_summary = analysis_summary
        self.relevance_score = relevance_score
        self.key_topics = key_topics
        self.salient_takeaways = salient_takeaways or []
        self.metadata = metadata or {}


class IRDocumentAnalyzer:
    """
    Analyzes IR documents to extract key information and determine relevance

    Uses Claude via AWS Bedrock to:
    1. Summarize document content
    2. Extract key topics/themes
    3. Generate salient takeaways for investors
    4. Calculate relevance to associated SEC filings
    """

    def __init__(self, config, db_connection=None, logger: Optional[PipelineLogger] = None):
        """
        Initialize IR document analyzer

        Args:
            config: PipelineConfig instance
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

        # Initialize Bedrock client
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=config.aws.region,
            aws_access_key_id=config.aws.access_key_id,
            aws_secret_access_key=config.aws.secret_access_key
        )

        self.model_id = config.aws.bedrock_model_id

        if self.logger:
            self.logger.info("Initialized IRDocumentAnalyzer")

    def _fetch_document_content(self, ir_document_id: str) -> Dict[str, Any]:
        """
        Fetch IR document from database

        Args:
            ir_document_id: UUID of ir_documents record

        Returns:
            Dictionary with document metadata and content
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT
                id,
                company_id,
                ticker,
                title,
                document_url,
                document_type,
                published_at,
                summary,
                raw_content
            FROM ir_documents
            WHERE id = %s
        """, (ir_document_id,))

        row = cursor.fetchone()
        cursor.close()

        if not row:
            raise DocumentNotFoundError(f"IR document {ir_document_id} not found")

        return {
            'id': row[0],
            'company_id': row[1],
            'ticker': row[2],
            'title': row[3],
            'document_url': row[4],
            'document_type': row[5],
            'published_at': row[6],
            'summary': row[7],
            'raw_content': row[8]
        }

    def _fetch_related_filing_context(self, ir_document_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch context about related filings for this IR document

        Args:
            ir_document_id: UUID of ir_documents record

        Returns:
            Dictionary with filing context, or None if no filings linked
        """
        if not self.db_connection:
            return None

        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT
                f.id,
                f.filing_type,
                f.filing_date,
                f.fiscal_year,
                f.fiscal_quarter,
                c.ticker,
                c.name,
                ifl.window_type,
                ifl.time_delta_hours
            FROM ir_filing_links ifl
            JOIN filings f ON ifl.filing_id = f.id
            JOIN companies c ON f.company_id = c.id
            WHERE ifl.ir_document_id = %s
            ORDER BY ABS(ifl.time_delta_hours) ASC
            LIMIT 1
        """, (ir_document_id,))

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        fiscal_period = f"Q{row[4]}" if row[4] else "FY"

        return {
            'filing_id': row[0],
            'filing_type': row[1],
            'filing_date': row[2],
            'fiscal_year': row[3],
            'fiscal_period': fiscal_period,
            'ticker': row[5],
            'company_name': row[6],
            'window_type': row[7],
            'time_delta_hours': row[8]
        }

    def _build_analysis_prompt(
        self,
        document: Dict[str, Any],
        filing_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for Claude to analyze IR document

        Args:
            document: IR document metadata and content
            filing_context: Optional context about related filing

        Returns:
            Formatted prompt string
        """
        ticker = document['ticker']
        title = document['title']
        doc_type = document['document_type']
        summary = document['summary'] or ''
        content = document['raw_content'] or summary

        # Truncate content if too long
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        prompt = f"""Analyze this investor relations document and provide structured insights.

DOCUMENT DETAILS:
- Company: {ticker}
- Title: {title}
- Type: {doc_type}
- URL: {document['document_url']}
- Published: {document['published_at'].strftime('%Y-%m-%d') if document['published_at'] else 'Unknown'}
"""

        if filing_context:
            prompt += f"""
RELATED SEC FILING:
- Filing Type: {filing_context['filing_type']}
- Fiscal Period: {filing_context['fiscal_period']} {filing_context['fiscal_year']}
- Filing Date: {filing_context['filing_date'].strftime('%Y-%m-%d')}
- Timing: {filing_context['window_type']} ({filing_context['time_delta_hours']}h from filing)
"""

        prompt += f"""
DOCUMENT CONTENT:
{content}

ANALYSIS REQUIRED:
Provide your analysis in the following JSON format:

{{
  "summary": "A concise 2-3 sentence summary of the key information",
  "key_topics": ["topic1", "topic2", "topic3"],
  "salient_takeaways": [
    "First key takeaway for investors",
    "Second key takeaway for investors",
    "Third key takeaway for investors"
  ],
  "relevance_score": 0.85,
  "relevance_reason": "Brief explanation of why this document is relevant to the filing"
}}

GUIDELINES:
1. **summary**: Concise overview of the document's main content (2-3 sentences)
2. **key_topics**: 3-5 main themes/topics (e.g., "Earnings Results", "Product Launch", "Strategic Update", "Guidance Revision")
3. **salient_takeaways**: 3-5 actionable insights investors should know about
4. **relevance_score**: 0.00-1.00 score indicating relevance to the SEC filing:
   - 0.90-1.00: Highly relevant (earnings results, major announcements)
   - 0.70-0.89: Moderately relevant (guidance updates, strategic info)
   - 0.50-0.69: Somewhat relevant (general news, product updates)
   - 0.00-0.49: Low relevance (routine announcements, minor updates)
5. **relevance_reason**: Brief explanation of the relevance score

Return ONLY the JSON object, no additional text.
"""

        return prompt

    def analyze_document(self, ir_document_id: str) -> IRAnalysisResult:
        """
        Analyze an IR document with Claude

        Args:
            ir_document_id: UUID of ir_documents record

        Returns:
            IRAnalysisResult with structured analysis

        Raises:
            AnalysisError: If analysis fails
        """
        start_time = time.time()

        try:
            # Fetch document
            document = self._fetch_document_content(ir_document_id)

            # Fetch related filing context
            filing_context = self._fetch_related_filing_context(ir_document_id)

            # Build prompt
            prompt = self._build_analysis_prompt(document, filing_context)

            if self.logger:
                self.logger.info(
                    f"Analyzing IR document: {document['title']}",
                    extra={'ir_document_id': ir_document_id, 'ticker': document['ticker']}
                )

            # Call Claude via Bedrock
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.3,  # Lower temperature for more consistent analysis
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            analysis_text = response_body['content'][0]['text']

            # Extract JSON from response
            # Claude might wrap JSON in markdown code blocks
            json_match = analysis_text.strip()
            if json_match.startswith('```'):
                # Remove markdown code block markers
                json_match = json_match.split('```')[1]
                if json_match.startswith('json'):
                    json_match = json_match[4:]
                json_match = json_match.strip()

            analysis_data = json.loads(json_match)

            # Calculate duration
            duration = time.time() - start_time

            # Track usage
            prompt_tokens = response_body['usage'].get('input_tokens', 0)
            completion_tokens = response_body['usage'].get('output_tokens', 0)

            if self.logger:
                self.logger.info(
                    f"Analyzed IR document: {document['title']}",
                    extra={
                        'ir_document_id': ir_document_id,
                        'relevance_score': analysis_data.get('relevance_score'),
                        'tokens': prompt_tokens + completion_tokens,
                        'duration_seconds': round(duration, 2)
                    }
                )

            # Create result
            return IRAnalysisResult(
                ir_document_id=ir_document_id,
                analysis_summary=analysis_data.get('summary', ''),
                relevance_score=float(analysis_data.get('relevance_score', 0.5)),
                key_topics=analysis_data.get('key_topics', []),
                salient_takeaways=analysis_data.get('salient_takeaways', []),
                metadata={
                    'relevance_reason': analysis_data.get('relevance_reason', ''),
                    'model_version': self.model_id,
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'analysis_duration_seconds': round(duration, 2)
                }
            )

        except ClientError as e:
            raise AnalysisError(f"Bedrock API error: {e}")
        except json.JSONDecodeError as e:
            raise AnalysisError(f"Failed to parse analysis JSON: {e}")
        except Exception as e:
            raise AnalysisError(f"Failed to analyze IR document: {e}")

    def save_analysis(self, result: IRAnalysisResult) -> bool:
        """
        Save analysis results to database

        Args:
            result: IRAnalysisResult to save

        Returns:
            True if saved successfully

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            # Prepare key_topics as JSONB
            key_topics_json = json.dumps(result.key_topics)

            # Prepare metadata
            metadata = {
                **result.metadata,
                'salient_takeaways': result.salient_takeaways
            }
            metadata_json = json.dumps(metadata)

            # Update ir_documents record
            cursor.execute("""
                UPDATE ir_documents
                SET
                    analyzed_at = %s,
                    analysis_summary = %s,
                    relevance_score = %s,
                    key_topics = %s,
                    status = 'analyzed',
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = %s
                WHERE id = %s
            """, (
                datetime.now(),
                result.analysis_summary,
                result.relevance_score,
                key_topics_json,
                metadata_json,
                datetime.now(),
                result.ir_document_id
            ))

            self.db_connection.commit()
            cursor.close()

            if self.logger:
                self.logger.info(
                    f"Saved analysis for IR document {result.ir_document_id}"
                )

            return True

        except Exception as e:
            if self.db_connection:
                self.db_connection.rollback()
            raise DatabaseError(f"Failed to save analysis: {e}")

    def analyze_pending_documents(
        self,
        limit: int = 50,
        company_id: Optional[str] = None
    ) -> int:
        """
        Analyze all pending IR documents

        Args:
            limit: Maximum number of documents to analyze
            company_id: Optional filter by company

        Returns:
            Number of documents analyzed
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        # Fetch pending documents
        cursor = self.db_connection.cursor()

        query = """
            SELECT id
            FROM ir_documents
            WHERE status = 'pending'
        """
        params = []

        if company_id:
            query += " AND company_id = %s"
            params.append(company_id)

        query += """
            ORDER BY published_at DESC
            LIMIT %s
        """
        params.append(limit)

        cursor.execute(query, params)
        document_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()

        if self.logger:
            self.logger.info(f"Found {len(document_ids)} pending IR documents to analyze")

        analyzed_count = 0

        for doc_id in document_ids:
            try:
                # Analyze document
                result = self.analyze_document(doc_id)

                # Save results
                self.save_analysis(result)

                analyzed_count += 1

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to analyze document {doc_id}",
                        exception=e
                    )
                continue

        if self.logger:
            self.logger.info(f"Successfully analyzed {analyzed_count}/{len(document_ids)} documents")

        return analyzed_count


class AnalysisError(Exception):
    """Raised when analysis fails"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass


class DocumentNotFoundError(Exception):
    """Raised when IR document not found"""
    pass

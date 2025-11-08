"""
Base analyzer class for AI-powered filing analysis

Provides abstract interface for analyzing SEC filings with Claude.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum


class AnalysisType(str, Enum):
    """Types of analysis we perform"""
    QUICK_SUMMARY = 'quick_summary'  # For TLDR (free tier)
    DEEP_ANALYSIS = 'deep_analysis'  # For paid tier


@dataclass
class AnalysisResult:
    """
    Result of analyzing a SEC filing

    This structure maps to the content table in the database.
    """
    filing_id: str

    # TLDR content (free tier)
    tldr_headline: str
    tldr_summary: str  # 2-3 sentences
    tldr_key_points: List[str]  # 3-5 bullet points

    # Deep analysis (paid tier)
    deep_headline: Optional[str] = None
    deep_intro: Optional[str] = None
    deep_sections: Optional[List[Dict[str, str]]] = None  # [{title, content}]
    deep_conclusion: Optional[str] = None

    # Metadata
    key_metrics: Optional[Dict[str, Any]] = None  # Financial metrics extracted
    sentiment_score: Optional[float] = None  # -1 to 1
    risk_factors: Optional[List[str]] = None
    opportunities: Optional[List[str]] = None

    # AI metadata
    model_version: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    analysis_duration_seconds: Optional[float] = None


class BaseAnalyzer(ABC):
    """
    Abstract base class for SEC filing analyzers

    Implementations should:
    1. Fetch filing content from S3 or database
    2. Extract and structure relevant text
    3. Call Claude via AWS Bedrock for analysis
    4. Parse and structure the response
    5. Save results to database

    Example:
        analyzer = ClaudeAnalyzer(config)
        result = analyzer.analyze_filing(
            filing_id='123',
            analysis_type=AnalysisType.DEEP_ANALYSIS
        )
        content_id = analyzer.save_to_database(result)
    """

    def __init__(self, config, db_connection=None, logger=None):
        """
        Initialize analyzer

        Args:
            config: PipelineConfig instance
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

    @abstractmethod
    def fetch_filing_content(self, filing_id: str) -> str:
        """
        Fetch filing content from S3 or database

        Args:
            filing_id: Database ID of filing

        Returns:
            Raw filing text content

        Raises:
            FetchError: If fetching fails
        """
        pass

    @abstractmethod
    def extract_relevant_sections(self, content: str) -> Dict[str, str]:
        """
        Extract relevant sections from filing

        Args:
            content: Raw filing text

        Returns:
            Dictionary of section names to content
            Example: {
                'business': '...',
                'risk_factors': '...',
                'md_and_a': '...',
                'financial_statements': '...'
            }

        Common 10-K sections:
        - Item 1: Business
        - Item 1A: Risk Factors
        - Item 7: MD&A (Management Discussion & Analysis)
        - Item 8: Financial Statements

        Common 10-Q sections:
        - Part I, Item 1: Financial Statements
        - Part I, Item 2: MD&A
        - Part II, Item 1A: Risk Factors
        """
        pass

    @abstractmethod
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

        This method should:
        1. Fetch filing content
        2. Extract relevant sections
        3. Build appropriate prompt for Claude
        4. Call Bedrock API
        5. Parse and structure response
        6. Return AnalysisResult
        """
        pass

    @abstractmethod
    def save_to_database(
        self,
        result: AnalysisResult,
        status: str = 'published'
    ) -> str:
        """
        Save analysis result to database

        Args:
            result: AnalysisResult to save
            status: Content status (draft, review, published)

        Returns:
            Database ID (UUID) of created content record

        Raises:
            DatabaseError: If save fails
        """
        pass

    def check_if_analyzed(self, filing_id: str) -> bool:
        """
        Check if filing has already been analyzed

        Args:
            filing_id: Database ID of filing

        Returns:
            True if content exists for this filing, False otherwise
        """
        if not self.db_connection:
            return False

        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT 1 FROM content WHERE filing_id = %s AND status = 'published'",
            (filing_id,)
        )
        exists = cursor.fetchone() is not None
        cursor.close()

        return exists

    def process_filing(
        self,
        filing_id: str,
        analysis_type: AnalysisType = AnalysisType.DEEP_ANALYSIS,
        skip_existing: bool = True
    ) -> Optional[str]:
        """
        Complete workflow: analyze filing and save to database

        Args:
            filing_id: Database ID of filing
            analysis_type: Type of analysis to perform
            skip_existing: Skip if content already exists

        Returns:
            Database ID of created content, or None if skipped

        This is a convenience method that orchestrates the full pipeline.
        """
        if self.logger:
            self.logger.info(
                f"Processing filing {filing_id} with {analysis_type.value}",
                extra={'filing_id': filing_id}
            )

        # Skip if already analyzed
        if skip_existing and self.check_if_analyzed(filing_id):
            if self.logger:
                self.logger.debug(
                    f"Skipping already analyzed filing {filing_id}"
                )
            return None

        try:
            # Analyze filing
            result = self.analyze_filing(filing_id, analysis_type)

            # Save to database
            content_id = self.save_to_database(result)

            if self.logger:
                self.logger.info(
                    f"Successfully analyzed filing {filing_id}",
                    extra={
                        'filing_id': filing_id,
                        'content_id': content_id,
                        'tokens': (result.prompt_tokens or 0) + (result.completion_tokens or 0)
                    }
                )

            return content_id

        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"Failed to analyze filing {filing_id}",
                    exception=e,
                    extra={'filing_id': filing_id}
                )
            raise


class AnalysisError(Exception):
    """Raised when analysis fails"""
    pass


class FetchError(Exception):
    """Raised when fetching filing content fails"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass

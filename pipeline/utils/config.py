"""
Configuration management for 10KAY pipeline

Loads environment variables and provides typed configuration objects
for different parts of the pipeline.
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')


@dataclass
class AWSConfig:
    """AWS service configuration"""
    region: str
    access_key_id: Optional[str]
    secret_access_key: Optional[str]
    s3_filings_bucket: str
    s3_audio_bucket: str
    bedrock_model_id: str

    @classmethod
    def from_env(cls) -> 'AWSConfig':
        """Load AWS config from environment variables"""
        return cls(
            region=os.getenv('AWS_REGION', 'us-east-1'),
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            s3_filings_bucket=os.getenv('AWS_S3_FILINGS_BUCKET', '10kay-filings'),
            s3_audio_bucket=os.getenv('AWS_S3_AUDIO_BUCKET', '10kay-audio'),
            bedrock_model_id=os.getenv('AWS_BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
        )


@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    url: str

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Load database config from environment variables"""
        url = os.getenv('DATABASE_URL')
        if not url:
            raise ValueError("DATABASE_URL environment variable is required")
        return cls(url=url)


@dataclass
class SECConfig:
    """SEC EDGAR API configuration"""
    base_url: str
    user_agent: str
    rate_limit_requests: int
    rate_limit_period: float  # seconds

    @classmethod
    def from_env(cls) -> 'SECConfig':
        """Load SEC config from environment variables"""
        # SEC requires a user agent with contact info
        email = os.getenv('CONTACT_EMAIL', 'contact@10kay.com')
        return cls(
            base_url='https://www.sec.gov',
            user_agent=f'10KAY SEC Filing Analyzer ({email})',
            rate_limit_requests=10,  # Max 10 requests per second per SEC guidelines
            rate_limit_period=1.0
        )


@dataclass
class PipelineConfig:
    """Main pipeline configuration"""
    aws: AWSConfig
    database: DatabaseConfig
    sec: SECConfig
    dry_run: bool
    max_retries: int
    retry_delay: float  # seconds

    @classmethod
    def from_env(cls) -> 'PipelineConfig':
        """Load full pipeline config from environment variables"""
        return cls(
            aws=AWSConfig.from_env(),
            database=DatabaseConfig.from_env(),
            sec=SECConfig.from_env(),
            dry_run=os.getenv('DRY_RUN', 'false').lower() == 'true',
            max_retries=int(os.getenv('MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('RETRY_DELAY', '2.0'))
        )


# Global config instance
_config: Optional[PipelineConfig] = None


def get_config() -> PipelineConfig:
    """Get global pipeline configuration (singleton)"""
    global _config
    if _config is None:
        _config = PipelineConfig.from_env()
    return _config

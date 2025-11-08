#!/usr/bin/env python3
"""
Test AWS Bedrock access with Claude Sonnet 4.5

This script verifies that:
1. AWS credentials are configured correctly
2. Bedrock service is accessible
3. Claude Sonnet 4.5 model is available
"""
import os
import json
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

# Load environment variables
load_dotenv('.env.local')

def test_bedrock_access():
    """Test Bedrock API access"""
    print("=" * 60)
    print("AWS Bedrock Access Test")
    print("=" * 60)
    print()

    # Check environment variables
    print("1. Checking environment variables...")
    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    # Try cross-region inference profile first, fall back to direct model ID
    model_id = os.getenv('AWS_BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')

    if not aws_key or not aws_secret:
        print("✗ AWS credentials not found in .env.local")
        print("  Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False

    print(f"✓ AWS_ACCESS_KEY_ID: {aws_key[:8]}...")
    print(f"✓ AWS_SECRET_ACCESS_KEY: ***")
    print(f"✓ AWS_REGION: {aws_region}")
    print(f"✓ Model ID: {model_id}")
    print()

    # Initialize Bedrock client
    print("2. Initializing Bedrock client...")
    try:
        bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=aws_region,
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret
        )
        print("✓ Bedrock client initialized")
        print()
    except Exception as e:
        print(f"✗ Failed to initialize Bedrock client: {e}")
        return False

    # Test API call with simple prompt
    print("3. Testing API call to Claude Sonnet 4.5...")
    test_prompt = "Hello! Please respond with a brief confirmation that you're working. Include your model name."

    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "temperature": 0.7,
            "messages": [
                {
                    "role": "user",
                    "content": test_prompt
                }
            ]
        }

        print(f"   Calling model: {model_id}")
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )

        # Parse response
        response_body = json.loads(response['body'].read())

        # Extract usage stats
        usage = response_body.get('usage', {})
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)

        # Extract response text
        content_blocks = response_body.get('content', [])
        if content_blocks:
            response_text = content_blocks[0].get('text', '')

            print("✓ API call successful!")
            print()
            print("Response from Claude:")
            print("-" * 60)
            print(response_text)
            print("-" * 60)
            print()
            print(f"Token usage: {input_tokens} input + {output_tokens} output = {input_tokens + output_tokens} total")
            print()

            return True
        else:
            print("✗ No content in response")
            return False

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        print(f"✗ Bedrock API error: {error_code}")
        print(f"  Message: {error_message}")
        print()

        if error_code == 'AccessDeniedException':
            print("  This likely means:")
            print("  - Model access hasn't been approved yet")
            print("  - Check AWS Bedrock Console > Model access")
            print("  - You may need to request access to Claude models")
        elif error_code == 'ValidationException':
            print("  This likely means:")
            print("  - The model ID is incorrect or not available in this region")
            print(f"  - Current model ID: {model_id}")
            print("  - Check available models in Bedrock Console")

        return False

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run Bedrock access test"""
    success = test_bedrock_access()

    print("=" * 60)
    if success:
        print("✅ Bedrock access test PASSED!")
        print()
        print("Next steps:")
        print("  - Your pipeline is ready to analyze SEC filings")
        print("  - Try: python3 pipeline/main.py --phase fetch --tickers AAPL")
    else:
        print("❌ Bedrock access test FAILED")
        print()
        print("Troubleshooting:")
        print("  1. Check AWS credentials in .env.local")
        print("  2. Verify Bedrock model access in AWS Console")
        print("  3. Ensure IAM user has bedrock:InvokeModel permission")
        print("  4. Confirm you're in a supported region (us-east-1, us-west-2)")
    print("=" * 60)

    return 0 if success else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

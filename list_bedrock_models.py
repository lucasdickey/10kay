#!/usr/bin/env python3
"""
List available Bedrock models

Shows all foundation models available in your AWS account.
"""
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

load_dotenv('.env.local')

def list_models():
    """List available Bedrock models"""
    print("=" * 80)
    print("Available Bedrock Models")
    print("=" * 80)
    print()

    aws_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')

    try:
        # Initialize Bedrock client (not bedrock-runtime)
        bedrock_client = boto3.client(
            'bedrock',
            region_name=aws_region,
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret
        )

        # List foundation models
        response = bedrock_client.list_foundation_models()

        # Filter for Anthropic models
        anthropic_models = [
            model for model in response['modelSummaries']
            if 'anthropic' in model['modelId'].lower()
        ]

        print(f"Found {len(anthropic_models)} Anthropic models:\n")

        for model in anthropic_models:
            print(f"Model ID: {model['modelId']}")
            print(f"  Name: {model.get('modelName', 'N/A')}")
            print(f"  Provider: {model.get('providerName', 'N/A')}")

            # Check if model supports streaming
            input_modalities = model.get('inputModalities', [])
            output_modalities = model.get('outputModalities', [])
            print(f"  Input: {', '.join(input_modalities)}")
            print(f"  Output: {', '.join(output_modalities)}")
            print()

        # Also try to list inference profiles
        print("\n" + "=" * 80)
        print("Inference Profiles (for cross-region inference)")
        print("=" * 80)
        print()

        try:
            profiles_response = bedrock_client.list_inference_profiles()
            profiles = profiles_response.get('inferenceProfileSummaries', [])

            # Filter for Anthropic/Claude profiles
            claude_profiles = [
                p for p in profiles
                if 'claude' in p.get('inferenceProfileName', '').lower() or
                   'anthropic' in p.get('inferenceProfileName', '').lower()
            ]

            if claude_profiles:
                print(f"Found {len(claude_profiles)} Claude inference profiles:\n")
                for profile in claude_profiles:
                    print(f"Profile ARN: {profile.get('inferenceProfileArn', 'N/A')}")
                    print(f"  Name: {profile.get('inferenceProfileName', 'N/A')}")
                    print(f"  Type: {profile.get('type', 'N/A')}")
                    print(f"  Status: {profile.get('status', 'N/A')}")
                    print()
            else:
                print("No Claude inference profiles found.")
                print("Note: Inference profiles may not be available in all regions.")

        except Exception as e:
            print(f"Could not list inference profiles: {e}")
            print("(This API may not be available in all regions)")

    except ClientError as e:
        print(f"✗ Error: {e.response['Error']['Code']}")
        print(f"  {e.response['Error']['Message']}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    list_models()

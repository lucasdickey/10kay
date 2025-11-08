#!/bin/bash

# Helper script to populate .env.local with AWS credentials from AWS CLI config

echo "🔧 10KAY Environment Setup Helper"
echo "=================================="
echo ""

# Check if AWS CLI is configured
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Get AWS credentials from CLI config
echo "📋 Checking your AWS CLI configuration..."
echo ""

# Get the current AWS profile (10kay-prod or specified)
AWS_PROFILE=${AWS_PROFILE:-10kay-prod}
echo "Using AWS profile: $AWS_PROFILE"
echo ""

# Test AWS credentials
echo "🔐 Testing AWS credentials..."
if aws sts get-caller-identity --profile $AWS_PROFILE &> /dev/null; then
    echo "✅ AWS credentials are valid!"
    aws sts get-caller-identity --profile $AWS_PROFILE
    echo ""
else
    echo "❌ AWS credentials test failed. Please configure AWS CLI first:"
    echo "   aws configure"
    exit 1
fi

# Get credentials from AWS CLI config
AWS_ACCESS_KEY=$(aws configure get aws_access_key_id --profile $AWS_PROFILE)
AWS_SECRET_KEY=$(aws configure get aws_secret_access_key --profile $AWS_PROFILE)
AWS_REGION=$(aws configure get region --profile $AWS_PROFILE)

# Default to us-east-1 if no region set
AWS_REGION=${AWS_REGION:-us-east-1}

echo "📝 Updating .env.local with your AWS credentials..."
echo ""

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "❌ .env.local not found. Creating from .env.example..."
    cp .env.example .env.local
fi

# Update .env.local with actual credentials
# Using sed to replace placeholder values
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY|" .env.local
    sed -i '' "s|AWS_SECRET_ACCESS_KEY=.*|AWS_SECRET_ACCESS_KEY=$AWS_SECRET_KEY|" .env.local
    sed -i '' "s|AWS_REGION=.*|AWS_REGION=$AWS_REGION|" .env.local
else
    # Linux
    sed -i "s|AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY|" .env.local
    sed -i "s|AWS_SECRET_ACCESS_KEY=.*|AWS_SECRET_ACCESS_KEY=$AWS_SECRET_KEY|" .env.local
    sed -i "s|AWS_REGION=.*|AWS_REGION=$AWS_REGION|" .env.local
fi

echo "✅ Updated .env.local with AWS credentials"
echo ""

# Verify permissions for required services
echo "🔍 Checking AWS permissions..."
echo ""

# Test RDS permissions
echo -n "RDS access: "
if aws rds describe-db-instances --max-items 1 --region $AWS_REGION &> /dev/null; then
    echo "✅"
else
    echo "❌ (you may need RDS permissions)"
fi

# Test S3 permissions
echo -n "S3 access: "
if aws s3 ls &> /dev/null; then
    echo "✅"
else
    echo "❌ (you may need S3 permissions)"
fi

# Test Bedrock permissions
echo -n "Bedrock access: "
if aws bedrock list-foundation-models --region $AWS_REGION &> /dev/null 2>&1; then
    echo "✅"
else
    echo "⚠️  (Bedrock access needs to be enabled in console)"
fi

echo ""
echo "=================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Create RDS database (see AWS_SETUP.md)"
echo "2. Create S3 buckets (see AWS_SETUP.md)"
echo "3. Enable Bedrock model access (see AWS_SETUP.md)"
echo "4. Update DATABASE_URL in .env.local after creating RDS"
echo ""

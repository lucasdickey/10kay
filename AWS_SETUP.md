# AWS Setup Guide for 10KAY

This guide walks you through setting up all required AWS resources for the 10KAY project:
- RDS PostgreSQL database
- S3 buckets for document storage
- Bedrock access for Claude API
- IAM permissions

**Prerequisites:**
- AWS account with $100k credits
- AWS CLI installed and configured
- Basic familiarity with AWS Console

---

## Table of Contents

1. [IAM User & Permissions](#1-iam-user--permissions)
2. [RDS PostgreSQL Setup](#2-rds-postgresql-setup)
3. [S3 Bucket Configuration](#3-s3-bucket-configuration)
4. [Bedrock Access](#4-bedrock-access)
5. [Environment Variables](#5-environment-variables)
6. [Testing Connections](#6-testing-connections)

---

## 1. IAM User & Permissions

### Create IAM User for the Pipeline

1. **Go to IAM Console** → Users → Create User
   - User name: `10kay-pipeline`
   - Access type: ✅ Programmatic access (no console access needed)

2. **Attach Policies:**
   - `AmazonRDSFullAccess` (for database access)
   - `AmazonS3FullAccess` (for document storage)
   - Create custom policy for Bedrock:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-*"
    }
  ]
}
```

3. **Save credentials:**
   - Download the CSV with `Access Key ID` and `Secret Access Key`
   - ⚠️ You'll only see the secret key once!

### Configure AWS CLI

```bash
aws configure --profile 10kay

# Enter:
# AWS Access Key ID: [from CSV]
# AWS Secret Access Key: [from CSV]
# Default region: us-east-1
# Default output format: json
```

**Test:**
```bash
aws sts get-caller-identity --profile 10kay
```

---

## 2. RDS PostgreSQL Setup

### Option A: AWS Console (Recommended for First-Time Setup)

1. **Go to RDS Console** → Create Database

2. **Engine Options:**
   - Engine type: PostgreSQL
   - Version: PostgreSQL 15.x or 16.x (latest stable)

3. **Templates:**
   - Select: **Free tier** (for dev) or **Production** (for prod)
   - For MVP with 50 users: Free tier db.t3.micro is sufficient

4. **Settings:**
   - DB instance identifier: `10kay-db`
   - Master username: `postgres` (or custom, e.g., `10kayadmin`)
   - Master password: **Generate strong password** (save it!)
   - ⚠️ **IMPORTANT:** Save this password securely - you'll need it for `DATABASE_URL`

5. **Instance Configuration:**
   - DB instance class: **db.t3.micro** (2 vCPU, 1 GB RAM)
   - Storage type: General Purpose SSD (gp3)
   - Allocated storage: **20 GB** (sufficient for beta)
   - ✅ Enable storage autoscaling (max 100 GB)

6. **Connectivity:**
   - **Compute resource:** Don't connect to EC2 instance
   - **Network type:** IPv4
   - **VPC:** Default VPC is fine
   - **Public access:** ✅ **Yes** (for development access)
     - For production, consider setting to No and using VPN/bastion
   - **VPC security group:** Create new → `10kay-db-sg`
   - **Availability Zone:** No preference

7. **Database Authentication:**
   - Choose: **Password authentication**

8. **Additional Configuration:**
   - Initial database name: `10kay`
   - ✅ Enable automated backups (retention: 7 days)
   - Backup window: Default
   - ✅ Enable Enhanced Monitoring (optional, uses credits)
   - ❌ Enable deletion protection (for dev - you can enable later)

9. **Click "Create database"**
   - ⏱️ Takes 5-10 minutes to provision

### Configure Security Group

**Important:** By default, RDS won't be accessible from your local machine or GitHub Actions.

1. **Go to EC2 Console** → Security Groups → Find `10kay-db-sg`

2. **Edit Inbound Rules:**
   - Click "Edit inbound rules"
   - Add rule:
     - Type: PostgreSQL
     - Protocol: TCP
     - Port: 5432
     - Source: **Your IP** (for local development)
     - Description: "Local development"

   - Add rule for GitHub Actions:
     - Type: PostgreSQL
     - Port: 5432
     - Source: `0.0.0.0/0` (⚠️ **Not ideal for production**, but needed for GitHub Actions)
     - Description: "GitHub Actions access"

   **Better option for production:** Use GitHub Actions with AWS credentials and connect via private subnet/VPN.

3. **Save rules**

### Get Database Endpoint

1. **Go to RDS Console** → Databases → `10kay-db`
2. **Copy the endpoint:** Something like `10kay-db.c9xx8xxxx.us-east-1.rds.amazonaws.com`
3. **Save this** - you'll use it in `DATABASE_URL`

### Option B: AWS CLI (Faster for Repeat Setups)

```bash
# Create security group
aws ec2 create-security-group \
  --group-name 10kay-db-sg \
  --description "Security group for 10KAY database" \
  --profile 10kay

# Allow PostgreSQL access (replace YOUR_IP)
aws ec2 authorize-security-group-ingress \
  --group-name 10kay-db-sg \
  --protocol tcp \
  --port 5432 \
  --cidr YOUR_IP/32 \
  --profile 10kay

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier 10kay-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username postgres \
  --master-user-password 'YOUR_STRONG_PASSWORD_HERE' \
  --allocated-storage 20 \
  --storage-type gp3 \
  --vpc-security-group-ids sg-xxxxxxxx \
  --publicly-accessible \
  --backup-retention-period 7 \
  --db-name 10kay \
  --profile 10kay
```

### Test Database Connection

Once the database is available (check RDS Console status):

```bash
# Install PostgreSQL client if needed
brew install postgresql  # macOS
# or: sudo apt-get install postgresql-client  # Linux

# Connect to database
psql "postgresql://postgres:YOUR_PASSWORD@10kay-db.c9xx8xxxx.us-east-1.rds.amazonaws.com:5432/10kay"

# Test query
SELECT version();

# Create test table
CREATE TABLE test (id SERIAL PRIMARY KEY, name TEXT);
INSERT INTO test (name) VALUES ('Hello from RDS!');
SELECT * FROM test;

# Exit
\q
```

✅ If this works, your RDS setup is complete!

---

## 3. S3 Bucket Configuration

### Create Buckets

We need two buckets:
1. `10kay-filings` - Store raw PDF documents from SEC
2. `10kay-audio` - Store generated audio files (Phase 5)

**⚠️ Bucket names must be globally unique!** If `10kay-filings` is taken, try `10kay-filings-{your-name}` or similar.

#### Option A: AWS Console

1. **Go to S3 Console** → Create bucket

2. **Bucket 1: Filings**
   - Bucket name: `10kay-filings` (or `10kay-filings-yourname`)
   - Region: `us-east-1` (same as RDS)
   - Object Ownership: ACLs disabled
   - Block Public Access: ✅ **Block all public access** (we'll use signed URLs)
   - Versioning: Disabled (optional: enable for safety)
   - Encryption: SSE-S3 (default)
   - Click "Create bucket"

3. **Bucket 2: Audio**
   - Same settings as above
   - Bucket name: `10kay-audio` (or `10kay-audio-yourname`)

#### Option B: AWS CLI

```bash
# Create filings bucket
aws s3 mb s3://10kay-filings --region us-east-1 --profile 10kay

# Create audio bucket
aws s3 mb s3://10kay-audio --region us-east-1 --profile 10kay

# Enable versioning (optional)
aws s3api put-bucket-versioning \
  --bucket 10kay-filings \
  --versioning-configuration Status=Enabled \
  --profile 10kay

# Set bucket encryption
aws s3api put-bucket-encryption \
  --bucket 10kay-filings \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --profile 10kay
```

### Test S3 Upload

```bash
# Test upload
echo "Test file" > test.txt
aws s3 cp test.txt s3://10kay-filings/test/ --profile 10kay

# List files
aws s3 ls s3://10kay-filings/ --profile 10kay

# Download file
aws s3 cp s3://10kay-filings/test/test.txt ./test-download.txt --profile 10kay

# Clean up
aws s3 rm s3://10kay-filings/test/test.txt --profile 10kay
rm test.txt test-download.txt
```

✅ If this works, S3 is configured correctly!

---

## 4. Bedrock Access

### Enable Bedrock Model Access

1. **Go to AWS Bedrock Console** → Model access
   - URL: https://console.aws.amazon.com/bedrock/

2. **Request access to Claude models:**
   - Click "Manage model access"
   - Find **Anthropic** section
   - Check the boxes for:
     - ✅ Claude 3.5 Sonnet
     - ✅ Claude 3 Opus (optional, for experiments)
     - ✅ Claude 3 Haiku (optional, for cheaper operations)

3. **Submit request**
   - Usually approved instantly for AWS accounts with credits
   - Check status - should show "Access granted"

4. **⚠️ Important:** Bedrock is only available in certain regions:
   - `us-east-1` (N. Virginia) ✅ Recommended
   - `us-west-2` (Oregon)
   - Others: check [AWS Bedrock regions](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html#bedrock-regions)

### Test Bedrock Access

Create a test script `test_bedrock.py`:

```python
import boto3
import json

# Initialize Bedrock client
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-east-1',
    # Uses credentials from AWS CLI profile or environment variables
)

# Test invocation
response = bedrock.invoke_model(
    modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [{
            "role": "user",
            "content": "Say 'Hello from Bedrock!' and nothing else."
        }]
    })
)

# Parse response
result = json.loads(response['body'].read())
print("Bedrock Response:", result['content'][0]['text'])
print("✅ Bedrock is working!")
```

Run it:

```bash
pip install boto3
AWS_PROFILE=10kay python test_bedrock.py
```

Expected output:
```
Bedrock Response: Hello from Bedrock!
✅ Bedrock is working!
```

✅ If this works, Bedrock is configured correctly!

---

## 5. Environment Variables

### Create `.env.local` for Next.js

Create `/path/to/10kay/.env.local`:

```bash
# AWS RDS PostgreSQL
DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@10kay-db.c9xx8xxxx.us-east-1.rds.amazonaws.com:5432/10kay"

# AWS Credentials (for S3 and Bedrock access from Next.js API routes)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# S3 Buckets
S3_BUCKET_FILINGS=10kay-filings
S3_BUCKET_AUDIO=10kay-audio

# Clerk (get from https://dashboard.clerk.com)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...

# Stripe (get from https://dashboard.stripe.com)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # Set up after creating webhook

# Resend (get from https://resend.com/api-keys)
RESEND_API_KEY=re_...

# App Config
NEXT_PUBLIC_APP_URL=http://localhost:3000  # Change to https://10kay.xyz in production

# ElevenLabs (Phase 5)
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

### Create `.env` for Python Pipeline

Create `/path/to/10kay/pipeline/.env`:

```bash
# AWS RDS PostgreSQL
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@10kay-db.c9xx8xxxx.us-east-1.rds.amazonaws.com:5432/10kay

# AWS Credentials
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# S3 Buckets
S3_BUCKET_FILINGS=10kay-filings
S3_BUCKET_AUDIO=10kay-audio

# Resend
RESEND_API_KEY=re_...

# App Config
APP_URL=https://10kay.xyz
```

### GitHub Actions Secrets

Add these secrets to your GitHub repository:

**Settings → Secrets and variables → Actions → New repository secret**

Add each of these:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `DATABASE_URL`
- `RESEND_API_KEY`
- `S3_BUCKET_FILINGS`
- `S3_BUCKET_AUDIO`

These will be used in the GitHub Actions workflow for automated processing.

---

## 6. Testing Connections

### Test Full Stack Locally

Create `test_connections.py` in the project root:

```python
import os
import boto3
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv('pipeline/.env')

def test_rds():
    """Test RDS PostgreSQL connection"""
    print("Testing RDS connection...")
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ RDS connected: {version[:50]}...")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ RDS connection failed: {e}")
        return False

def test_s3():
    """Test S3 bucket access"""
    print("\nTesting S3 access...")
    try:
        s3 = boto3.client('s3', region_name=os.getenv('AWS_REGION'))
        bucket = os.getenv('S3_BUCKET_FILINGS')

        # Test write
        s3.put_object(Bucket=bucket, Key='test/connection_test.txt', Body=b'Test')
        print(f"✅ S3 write successful to {bucket}")

        # Test read
        obj = s3.get_object(Bucket=bucket, Key='test/connection_test.txt')
        content = obj['Body'].read()
        print(f"✅ S3 read successful: {content}")

        # Cleanup
        s3.delete_object(Bucket=bucket, Key='test/connection_test.txt')
        print(f"✅ S3 cleanup successful")

        return True
    except Exception as e:
        print(f"❌ S3 access failed: {e}")
        return False

def test_bedrock():
    """Test Bedrock Claude access"""
    print("\nTesting Bedrock access...")
    try:
        import json
        bedrock = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION'))

        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 50,
                "messages": [{
                    "role": "user",
                    "content": "Say 'Bedrock connected!' and nothing else."
                }]
            })
        )

        result = json.loads(response['body'].read())
        message = result['content'][0]['text']
        print(f"✅ Bedrock connected: {message}")
        return True
    except Exception as e:
        print(f"❌ Bedrock access failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing AWS connections for 10KAY...\n")

    rds_ok = test_rds()
    s3_ok = test_s3()
    bedrock_ok = test_bedrock()

    print("\n" + "="*50)
    if rds_ok and s3_ok and bedrock_ok:
        print("✅ All AWS services connected successfully!")
        print("You're ready to start development.")
    else:
        print("❌ Some connections failed. Check errors above.")
    print("="*50)
```

Run it:

```bash
pip install boto3 psycopg2-binary python-dotenv
python test_connections.py
```

Expected output:

```
🔧 Testing AWS connections for 10KAY...

Testing RDS connection...
✅ RDS connected: PostgreSQL 15.4 on x86_64-pc-linux-gnu...

Testing S3 access...
✅ S3 write successful to 10kay-filings
✅ S3 read successful: b'Test'
✅ S3 cleanup successful

Testing Bedrock access...
✅ Bedrock connected: Bedrock connected!

==================================================
✅ All AWS services connected successfully!
You're ready to start development.
==================================================
```

---

## Summary Checklist

Before proceeding to implementation, verify:

- [x] IAM user created with appropriate permissions
- [x] AWS CLI configured with profile
- [x] RDS PostgreSQL instance running and accessible
- [x] Security group allows access from development machine
- [x] S3 buckets created (`10kay-filings`, `10kay-audio`)
- [x] Bedrock model access granted for Claude 3.5 Sonnet
- [x] `.env.local` created for Next.js
- [x] `pipeline/.env` created for Python
- [x] GitHub Actions secrets configured
- [x] All connections tested successfully

---

## Troubleshooting

### "Could not connect to RDS"

**Check:**
1. RDS instance is in "Available" state (not "Creating")
2. Security group allows inbound on port 5432 from your IP
3. Database endpoint is correct in `DATABASE_URL`
4. Username and password are correct
5. Database name `10kay` was created during setup

**Debug:**
```bash
# Test network connectivity
telnet 10kay-db.xxxxx.us-east-1.rds.amazonaws.com 5432

# Should see "Connected" - if not, it's a security group issue
```

### "S3 Access Denied"

**Check:**
1. IAM user has `AmazonS3FullAccess` policy
2. Bucket names are correct in environment variables
3. AWS credentials are correctly set

**Debug:**
```bash
# Test AWS credentials
aws sts get-caller-identity --profile 10kay

# List buckets
aws s3 ls --profile 10kay
```

### "Bedrock Model Not Found"

**Check:**
1. Bedrock model access request is approved (check Bedrock console)
2. Using correct region (`us-east-1`)
3. Model ID is exact: `anthropic.claude-3-5-sonnet-20241022-v2:0`

**Debug:**
```bash
# List available models
aws bedrock list-foundation-models --region us-east-1 --profile 10kay
```

---

## Cost Monitoring

Even though you have credits, it's good practice to monitor usage:

### Set up AWS Budgets

1. Go to **AWS Billing Console** → Budgets
2. Create budget:
   - Type: Cost budget
   - Amount: $100/month (adjust as needed)
   - Alert threshold: 80%
   - Email notification: your email

### Check Credit Usage

1. Go to **AWS Billing Console** → Credits
2. View remaining credits and expiration (June 2026)

### Estimate Monthly Costs (if paying)

With your current setup:
- RDS db.t3.micro: ~$15/month
- S3 storage (1GB): ~$0.02/month
- Bedrock (50 companies × 4 filings/year): ~$15/month
- **Total: ~$30/month** (all covered by credits)

---

## Next Steps

Once all tests pass:

1. ✅ Proceed to **Phase 0** implementation (see TECHNICAL_SPEC.md)
2. Run database migrations (see next guide)
3. Start building the Next.js application

**Documentation End**

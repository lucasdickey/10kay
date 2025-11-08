# IAM User Setup for 10KAY

**Goal:** Create a dedicated IAM user with minimal required permissions for the 10KAY project.

**Time:** ~5 minutes

---

## Step 1: Create IAM User (AWS Console)

1. **Go to IAM Console:** https://console.aws.amazon.com/iam/

2. **Users → Create User**
   - User name: `10kay-prod`
   - Access type: ✅ **Programmatic access only** (no console access needed)
   - Click **Next**

3. **Set Permissions**

   **Option A - Quick (Using AWS Managed Policies):**
   - Click "Attach policies directly"
   - Search and select these policies:
     - ✅ `AmazonRDSFullAccess`
     - ✅ `AmazonS3FullAccess`
   - Click **Next**

   **Option B - Secure (Custom Policy - Recommended):**
   - Click "Create policy" → JSON tab
   - Paste the custom policy below
   - Name it: `10kay-prod-policy`
   - Go back and attach this policy to the user

4. **Review and Create**
   - Review the user details
   - Click **Create user**

5. **⚠️ CRITICAL: Save Credentials**
   - AWS will show you the credentials **ONLY ONCE**
   - Click **Download .csv**
   - Or copy/paste:
     - Access Key ID (starts with `AKIA...`)
     - Secret Access Key (long random string)
   - Store these securely!

---

## Custom IAM Policy (Option B - Most Secure)

This policy gives 10KAY exactly what it needs, nothing more:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RDSAccess",
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBInstance",
        "rds:DescribeDBInstances",
        "rds:ModifyDBInstance",
        "rds:DeleteDBInstance",
        "rds:CreateDBSnapshot",
        "rds:DescribeDBSnapshots",
        "rds:RestoreDBInstanceFromDBSnapshot",
        "rds:AddTagsToResource",
        "rds:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RDSSecurityGroup",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeSecurityGroups",
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:PutBucketVersioning",
        "s3:GetBucketVersioning",
        "s3:PutEncryptionConfiguration",
        "s3:GetEncryptionConfiguration"
      ],
      "Resource": [
        "arn:aws:s3:::10kay-*",
        "arn:aws:s3:::10kay-*/*"
      ]
    },
    {
      "Sid": "BedrockAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    },
    {
      "Sid": "MarketplaceAccess",
      "Effect": "Allow",
      "Action": [
        "aws-marketplace:ViewSubscriptions"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["us-east-1", "us-west-2"]
        }
      }
    }
  ]
}
```

**What this policy allows:**
- ✅ Create/manage RDS databases
- ✅ Create/manage S3 buckets starting with `10kay-`
- ✅ Invoke Bedrock models (Claude)
- ✅ Manage security groups for RDS access
- ❌ Nothing else (no EC2, Lambda, IAM, etc.)

---

## Step 2: Configure AWS CLI with New Credentials

Once you have the Access Key ID and Secret Access Key:

```bash
# Configure AWS CLI with the new 10kay-prod credentials
aws configure --profile 10kay

# You'll be prompted:
# AWS Access Key ID: [paste your AKIA... key]
# AWS Secret Access Key: [paste your secret key]
# Default region: us-west-2  (or us-east-1, your choice)
# Default output format: json
```

**Test it:**
```bash
# Test credentials work
aws sts get-caller-identity --profile 10kay

# Should show:
# {
#     "UserId": "AIDA...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/10kay-prod"
# }
```

---

## Step 3: Update .env.local

Get your credentials into the project:

```bash
# Run the setup helper script with the new profile
AWS_PROFILE=10kay ./setup_env.sh
```

Or manually edit `.env.local`:

```bash
AWS_ACCESS_KEY_ID=AKIA...  # Your new 10kay-prod Access Key
AWS_SECRET_ACCESS_KEY=...  # Your new 10kay-prod Secret Key
AWS_REGION=us-west-2       # Or us-east-1 if you prefer
```

---

## Step 4: Store in GitHub Secrets

For GitHub Actions to work, add these as repository secrets:

1. **Go to GitHub:** https://github.com/lucasdickey/10kay/settings/secrets/actions

2. **Add these secrets:**
   - **Name:** `AWS_ACCESS_KEY_ID` → **Value:** [your AKIA... key]
   - **Name:** `AWS_SECRET_ACCESS_KEY` → **Value:** [your secret key]
   - **Name:** `AWS_REGION` → **Value:** `us-west-2` (or your region)

**Later (after creating RDS/S3):**
   - `DATABASE_URL`
   - `S3_BUCKET_FILINGS`
   - `S3_BUCKET_AUDIO`
   - `RESEND_API_KEY`

---

## Region Recommendation

**Two options:**

| Region | Pros | Cons |
|--------|------|------|
| `us-east-1` | • Bedrock has most models<br>• Lowest costs<br>• Matches spec | • Further from you if you're West Coast |
| `us-west-2` | • Bedrock available<br>• Closer to you geographically<br>• Slightly lower latency | • Occasionally slower to get new AWS features |

**Recommendation:** Use **`us-west-2`** since you already have it configured. Bedrock Claude is available there, and for 50 beta users, latency differences are negligible.

---

## Verification Checklist

Before proceeding to RDS/S3 setup:

- [ ] IAM user `10kay-prod` created
- [ ] Downloaded credentials CSV (saved securely)
- [ ] Configured AWS CLI: `aws configure --profile 10kay`
- [ ] Tested credentials: `aws sts get-caller-identity --profile 10kay` works
- [ ] Updated `.env.local` with new credentials
- [ ] Added secrets to GitHub repository

---

## Security Best Practices

**DO:**
- ✅ Keep credentials in `.env.local` (gitignored)
- ✅ Use GitHub Secrets for CI/CD
- ✅ Rotate credentials every 90 days
- ✅ Download credentials CSV and store in password manager

**DON'T:**
- ❌ Commit credentials to git
- ❌ Share credentials in chat/email/Slack
- ❌ Use root account credentials
- ❌ Give overly broad permissions

**If credentials leak:**
```bash
# Immediately deactivate in IAM Console:
# IAM → Users → 10kay-prod → Security credentials → Deactivate
# Then create new access key
```

---

## Next Steps

Once IAM user is set up:
1. ✅ Create RDS PostgreSQL database → See AWS_SETUP.md Section 2
2. ✅ Create S3 buckets → See AWS_SETUP.md Section 3
3. ✅ Enable Bedrock access → See AWS_SETUP.md Section 4

---

**End of IAM Setup**

#!/bin/bash
# Run this from local machine or CloudShell (not EC2)
# Make sure AWS CLI is configured with your credentials

REGION="ap-south-1"  # change if your DynamoDB region differs

echo "Creating resume_counter table..."
aws dynamodb create-table \
  --table-name resume_counter \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION

echo "Creating resume_geo_logs table..."
aws dynamodb create-table \
  --table-name resume_geo_logs \
  --attribute-definitions \
    AttributeName=visit_id,AttributeType=S \
    AttributeName=visited_at,AttributeType=S \
  --key-schema \
    AttributeName=visit_id,KeyType=HASH \
    AttributeName=visited_at,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION

echo "Done. Tables will be ACTIVE in ~30 seconds."
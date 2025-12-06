#!/bin/bash
# Initial deployment script for first-time ECR push
#
# This script is needed because Terraform creates the Lambda function
# with a reference to the ECR image, but the image doesn't exist yet.
# Run this once after Terraform creates the infrastructure.
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - Docker running
# - ECR repository created by Terraform

set -euo pipefail

# Configuration - update these after Terraform apply
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REPOSITORY="productivity-service"
LAMBDA_FUNCTION_NAME="productivity-service"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo "=== Initial Deployment for ${ECR_REPOSITORY} ==="
echo "AWS Account: ${AWS_ACCOUNT_ID}"
echo "Region: ${AWS_REGION}"
echo "ECR Repository: ${ECR_URI}"
echo ""

# Login to ECR
echo "1. Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Build the image
echo ""
echo "2. Building Docker image..."
docker build -t "${ECR_REPOSITORY}:latest" .

# Tag for ECR
echo ""
echo "3. Tagging image for ECR..."
docker tag "${ECR_REPOSITORY}:latest" "${ECR_URI}:latest"
docker tag "${ECR_REPOSITORY}:latest" "${ECR_URI}:initial"

# Push to ECR
echo ""
echo "4. Pushing image to ECR..."
docker push "${ECR_URI}:latest"
docker push "${ECR_URI}:initial"

# Update Lambda function
echo ""
echo "5. Updating Lambda function..."
aws lambda update-function-code \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --image-uri "${ECR_URI}:latest" \
  --region "${AWS_REGION}"

# Wait for update to complete
echo ""
echo "6. Waiting for Lambda update to complete..."
aws lambda wait function-updated \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Your service is now deployed. Get the API URL with:"
echo "  aws lambda get-function-url-config --function-name ${LAMBDA_FUNCTION_NAME}"
echo ""
echo "Or check the API Gateway URL in the AWS Console."
echo ""
echo "Future deployments will happen automatically via GitHub Actions."

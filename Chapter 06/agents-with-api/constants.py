"""
Constants for Bedrock Agents implementation

Note: This constants.py file is used by the main application files (agents_helper_util.py, notebooks).
"""

# AWS Region Configuration
AWS_REGION = "us-west-2"

# Lambda Configuration
PYTHON_RUNTIME = 'python3.12'
LAMBDA_TIMEOUT = 60

# DynamoDB Configuration
TABLE_NAME = 'orders'
TABLE_PARTITION_KEY = 'order_id'

# Lambda Function Configuration
ORDER_LAMBDA_CODE_FILE_NAME = 'order_lambda'

# Model Configuration . See https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html for more information
AGENT_FOUNDATION_MODEL = "anthropic.claude-3-7-sonnet-20250219-v1:0"

# IMPORTANT: Knowledge Base Configuration - Replace with your knowledge base id created in Chapter 5
# Refer https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-create.html for more information.
CUSTOMER_SUPPORT_KB_ID = "KAXXXX5ONA"  

import boto3
import json
import time
import zipfile
from io import BytesIO
import logging
from constants import (
    AWS_REGION, PYTHON_RUNTIME, LAMBDA_TIMEOUT, 
    TABLE_NAME, TABLE_PARTITION_KEY, ORDER_LAMBDA_CODE_FILE_NAME
)

logger = logging.getLogger()
session = boto3.session.Session()
region = AWS_REGION
dynamodb_client = boto3.client('dynamodb', region)
dynamodb_resource = boto3.resource('dynamodb', region)
lambda_client = boto3.client('lambda', region)
bedrock_agent_client = boto3.client('bedrock-agent', region)
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', region)
iam_client = boto3.client('iam',region)
sts_client = boto3.client('sts', region)
account_id = sts_client.get_caller_identity()["Account"]


def create_dynamodb(table_name=TABLE_NAME, partition_key=TABLE_PARTITION_KEY):
    """
        Creates a DynamoDB table with the specified name, and partition key. If table already exists, return
    """
    
    # Check if the table already exists
    existing_tables = dynamodb_client.list_tables()['TableNames']
    if TABLE_NAME in existing_tables:
        logger.debug(f"Table '{TABLE_NAME}' already exists.")
        return
        
    table = dynamodb_resource.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': partition_key,
                'KeyType': 'HASH'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': partition_key,
                'AttributeType': 'S'
            }
        ],
        BillingMode='PAY_PER_REQUEST'  # Use on-demand capacity mode
    )

    # Wait for the table to be created
    logger.info(f'Creating table {table_name}...')
    table.wait_until_exists()
    logger.info(f'Table {table_name} created successfully!')
    return


def create_lambda(lambda_function_name, lambda_iam_role, lambda_code_file_name=ORDER_LAMBDA_CODE_FILE_NAME):
    """
        Package up the lambda function code
    """
   
    s = BytesIO()
    z = zipfile.ZipFile(s, 'w')
    # Lambda files are in the same directory as this utility file
    z.write(f"{lambda_code_file_name}.py")  # Include the file with the dynamic name
    
    z.close()
    zip_content = s.getvalue()

    # Create Lambda Function
    lambda_function = lambda_client.create_function(
        FunctionName=lambda_function_name,
        Runtime=PYTHON_RUNTIME,
        Timeout=LAMBDA_TIMEOUT,
        Role=lambda_iam_role['Role']['Arn'],
        Code={'ZipFile': zip_content},
        Handler=f"{lambda_code_file_name}.lambda_handler"
    )
    return lambda_function



def create_lambda_role(agent_name, dynamodb_table_name=TABLE_NAME):
    """
        Create IAM role and required policies for Lambda funciton
    """
    lambda_function_role = f'{agent_name}-lambda-role'
    
    # Create IAM Role for the Lambda function
    try:
        assume_role_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        assume_role_policy_document_json = json.dumps(assume_role_policy_document)

        lambda_iam_role = iam_client.create_role(
            RoleName=lambda_function_role,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        lambda_iam_role = iam_client.get_role(RoleName=lambda_function_role)

    # Attach the AWSLambdaBasicExecutionRole policy
    iam_client.attach_role_policy(
        RoleName=lambda_function_role,
        PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
    )
    
    ## Create DynamoDB access policy if not alredy exists
    dynamodb_access_policy_name = f'{agent_name}-dynamodb-policy'

    # List existing policies
    existing_policies = iam_client.list_policies(Scope='Local')['Policies']
    existing_policy_names = [policy['PolicyName'] for policy in existing_policies]

    # Check if the policy already exists
    if dynamodb_access_policy_name in existing_policy_names:
        logger.debug(f"Policy '{dynamodb_access_policy_name}' already exists.")
    else:
        # Create a policy to grant access to the DynamoDB table
        dynamodb_access_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:DeleteItem"
                    ],
                    "Resource": "arn:aws:dynamodb:{}:{}:table/{}".format(
                        region, account_id, dynamodb_table_name
                    )
                }
            ]
        }

        # Create the policy
        dynamodb_access_policy_json = json.dumps(dynamodb_access_policy)
        dynamodb_access_policy_response = iam_client.create_policy(
            PolicyName=dynamodb_access_policy_name,
            PolicyDocument=dynamodb_access_policy_json
        )
        logger.debug(f"Policy '{dynamodb_access_policy_name}' created successfully.")

        # Attach the policy to the Lambda function's role
        iam_client.attach_role_policy(
            RoleName=lambda_function_role,
            PolicyArn=dynamodb_access_policy_response['Policy']['Arn']
        )
        logger.debug("Policy attached to the Lambda function's role.")

    return lambda_iam_role


def create_agent_role_and_policies(agent_name, agent_foundation_model, kb_id=None):
    agent_bedrock_allow_policy_name = f"{agent_name}-ba"
    agent_role_name = f'AmazonBedrockExecutionRoleForAgents_{agent_name}'
    # Create IAM policies for agent
    statements = [
        {
            "Sid": "AmazonBedrockAgentBedrockFoundationModelPolicy",
            "Effect": "Allow",
            "Action": "bedrock:InvokeModel",
            "Resource": [
                f"arn:aws:bedrock:{region}::foundation-model/{agent_foundation_model}"
            ]
        }
    ]
    # add Knowledge Base retrieve and retrieve and generate permissions if agent has KB attached to it
    if kb_id:
        statements.append(
            {
                "Sid": "QueryKB",
                "Effect": "Allow",
                "Action": [
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate"
                ],
                "Resource": [
                    f"arn:aws:bedrock:{region}:{account_id}:knowledge-base/{kb_id}"
                ]
            }
        )

    bedrock_agent_bedrock_allow_policy_statement = {
        "Version": "2012-10-17",
        "Statement": statements
    }

    bedrock_policy_json = json.dumps(bedrock_agent_bedrock_allow_policy_statement)

    agent_bedrock_policy = iam_client.create_policy(
        PolicyName=agent_bedrock_allow_policy_name,
        PolicyDocument=bedrock_policy_json
    )

    # Create IAM Role for the agent and attach IAM policies
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }]
    }

    assume_role_policy_document_json = json.dumps(assume_role_policy_document)
    agent_role = iam_client.create_role(
        RoleName=agent_role_name,
        AssumeRolePolicyDocument=assume_role_policy_document_json
    )

    # Pause to make sure role is created
    time.sleep(10)

    iam_client.attach_role_policy(
        RoleName=agent_role_name,
        PolicyArn=agent_bedrock_policy['Policy']['Arn']
    )
    return agent_role


def delete_agent_roles_and_policies(agent_name):
    agent_bedrock_allow_policy_name = f"{agent_name}-ba"
    agent_role_name = f'AmazonBedrockExecutionRoleForAgents_{agent_name}'
    dynamodb_access_policy_name = f'{agent_name}-dynamodb-policy'
    lambda_function_role = f'{agent_name}-lambda-role'

    for policy in [agent_bedrock_allow_policy_name]:
        try:
            iam_client.detach_role_policy(
                RoleName=agent_role_name,
                PolicyArn=f'arn:aws:iam::{account_id}:policy/{policy}'
            )
        except Exception as e:
            print(f"Could not detach {policy} from {agent_role_name}")
            print(e)

    for policy in [dynamodb_access_policy_name]:
        try:
            iam_client.detach_role_policy(
                RoleName=lambda_function_role,
                PolicyArn=f'arn:aws:iam::{account_id}:policy/{policy}'
            )
        except Exception as e:
            print(f"Could not detach {policy} from {lambda_function_role}")
            print(e)

    try:
        iam_client.detach_role_policy(
            RoleName=lambda_function_role,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
    except Exception as e:
        print(f"Could not detach AWSLambdaBasicExecutionRole from {lambda_function_role}")
        print(e)

    for role_name in [agent_role_name, lambda_function_role]:
        try:
            iam_client.delete_role(
                RoleName=role_name
            )
        except Exception as e:
            print(f"Could not delete role {role_name}")
            print(e)

    for policy in [agent_bedrock_allow_policy_name, dynamodb_access_policy_name]:
        try:
            iam_client.delete_policy(
                PolicyArn=f'arn:aws:iam::{account_id}:policy/{policy}'
            )
        except Exception as e:
            print(f"Could not delete policy {policy}")
            print(e)


def clean_up_resources(
        table_name, lambda_function, lambda_function_name, agent_action_group_response, agent_functions,
        agent_id, kb_id, alias_id
):
    action_group_id = agent_action_group_response['agentActionGroup']['actionGroupId']
    action_group_name = agent_action_group_response['agentActionGroup']['actionGroupName']
    # Delete Agent Action Group, Agent Alias, and Agent
    try:
        bedrock_agent_client.update_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupId= action_group_id,
            actionGroupName=action_group_name,
            actionGroupExecutor={
                'lambda': lambda_function['FunctionArn']
            },
            functionSchema={
                'functions': agent_functions
            },
            actionGroupState='DISABLED',
        )
        bedrock_agent_client.disassociate_agent_knowledge_base(
            agentId=agent_id,
            agentVersion='DRAFT',
            knowledgeBaseId=kb_id
        )
        bedrock_agent_client.delete_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupId=action_group_id
        )
        bedrock_agent_client.delete_agent_alias(
            agentAliasId=alias_id,
            agentId=agent_id
        )
        bedrock_agent_client.delete_agent(agentId=agent_id)
        print(f"Agent {agent_id}, Agent Alias {alias_id}, and Action Group have been deleted.")
    except Exception as e:
        print(f"Error deleting Agent resources: {e}")

    # Delete Lambda function
    try:
        lambda_client.delete_function(FunctionName=lambda_function_name)
        print(f"Lambda function {lambda_function_name} has been deleted.")
    except Exception as e:
        print(f"Error deleting Lambda function {lambda_function_name}: {e}")

    # Delete DynamoDB table
    try:
        dynamodb_client.delete_table(TableName=table_name)
        print(f"Table {table_name} is being deleted...")
        waiter = dynamodb_client.get_waiter('table_not_exists')
        waiter.wait(TableName=table_name)
        print(f"Table {table_name} has been deleted.")
    except Exception as e:
        print(f"Error deleting table {table_name}: {e}")
        
#############################################################################
## Some of the code in this utility is sourced from https://github.com/aws-samples/amazon-bedrock-samples/blob/main/agents-for-bedrock/features-examples/05-create-agent-with-knowledge-base-and-action-group/agent.py
## Modified to fit the needs of this project
#############################################################################
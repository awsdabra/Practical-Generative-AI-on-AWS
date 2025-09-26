import boto3
import json
import logging
import random
import string
from datetime import datetime, timedelta
import time
from botocore.exceptions import ClientError

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Client
dynamodb = boto3.client('dynamodb')
TABLE_NAME = "orders"

# Get order details
def get_order_details(order_id):
    try:
        response = dynamodb.get_item(
            TableName=TABLE_NAME,
            Key={'order_id': {'S': order_id}}
        )
        if 'Item' in response:
            return response['Item']
        else:
            print(f"Order '{order_id}' not found.")
            return None
    except ClientError as e:
        print(f"Error getting order details: {e.response['Error']['Message']}")
        return None

# Cancel an order
def cancel_order(order_id):
    try:
        order_data = get_order_details(order_id)
        if order_data:
            order_data['status'] = {'S': 'Cancelled'}
            dynamodb.put_item(
                TableName=TABLE_NAME,
                Item=order_data
            )
            print(f"Order '{order_id}' has been cancelled.")
        else:
            print(f"Order '{order_id}' not found.")
    except ClientError as e:
        print(f"Error cancelling order: {e.response['Error']['Message']}")
        
# Create a new order
def place_order(product_name, quantity, shipping_address, payment_method, name):
    order_id = generate_order_id()
    product_id = generate_product_id()
    delivery_date = (datetime.combine(datetime.now().date(), datetime.min.time()) + timedelta(days=10)).date().isoformat()
    
    order_data = {
        'order_id': {'S': order_id},
        'name': {'S': name},
        'product_id': {'S': product_id},
        'item': {'S': product_name},
        'quantity': {'N': quantity},
        'shipping_address': {'S': shipping_address},
        'payment_method': {'S': payment_method},
        'status': {'S': 'Processing'},
        'delivery_date': {'S': delivery_date},
    }

    try:
        dynamodb.put_item(
            TableName=TABLE_NAME,
            Item=order_data
        )
        logger.info(f"Order '{order_data['order_id']}' created successfully.")
        return f"Order placed successfully! Order ID: {order_id}, Product ID: {product_id}, Product Name: {product_name}, Quantity: {quantity}, Estimated Delivery Date: {delivery_date}"

    except ClientError as e:
        logger.debug(f"Error creating order: {e.response['Error']['Message']}")
        return None

# Helper function to get the current timestamp
def get_current_timestamp():
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())

# Helper function to generate a random order ID
def generate_order_id():
    order_id_number = ''.join(random.choices(string.digits, k=5))
    return f"ORD{order_id_number}"

# Helper function to generate a random product ID
def generate_product_id():
    product_id_number = ''.join(random.choices(string.digits, k=5))
    return f"PROD{product_id_number}"

# Primary Handler 
def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))
    
    # Extract parameters from the event
    agent = event['agent']
    actionGroup = event['actionGroup']
    function = event['function']
    parameters = {param['name']: param['value'] for param in event.get('parameters', [])}
    
    # Extract sessionAttributes or promptSessionAttributes if present. These can be useful for providing temporal context for the agent
    session_attributes = event.get('sessionAttributes', {})
    prompt_session_attributes = event.get('promptSessionAttributes', {})

    # Optionally, you can use the session_attributes or prompt_session_attributes to retrieve missing or additional data needed for the function
    # session_attribute persists over a session between a user and the agent while prompt_session_attribute is only available during the single turn of a conversation with the agent.
    # Refer https://docs.aws.amazon.com/bedrock/latest/userguide/agents-session-state.html for more information.
    # For example, if the customer_name or shipping_address is missing in the user provided parameters, you can try to retrieve it from the agent context using session_attributes
    if 'customer_name' not in parameters and 'customer_name' in session_attributes:
        parameters['customer_name'] = session_attributes['customer_name']
        
    if 'shipping_address' not in parameters and 'shipping_address' in session_attributes:
        parameters['shipping_address'] = session_attributes['shipping_address']
        
    if 'payment_method' not in parameters and 'payment_method' in session_attributes:
        parameters['payment_method'] = session_attributes['payment_method']

    # Business logic            
    if actionGroup == 'order-action-group':
        if function == 'retrieve-order-tracking-info':
            order_id = parameters.get('order_id')
            if order_id:
                order_data = get_order_details(order_id)
                responseBody = {'TEXT': {'body': json.dumps(order_data)}}
            else:
                responseBody = {'TEXT': {'body': "Order ID is required"}}
        elif function == 'cancel-order':
            order_id = parameters.get('order_id')
            if order_id:
                cancel_order(order_id)
                responseBody = {'TEXT': {'body': "Order cancelled"}}
            else:
                responseBody = {'TEXT': {'body': "Order ID is required"}}
        elif function == 'place-order':
            # Extract order details from parameters
            product_name = parameters.get('product_name')
            name = parameters.get('name')
            quantity = parameters.get('quantity', '1')
            shipping_address = parameters.get('shipping_address')
            payment_method = parameters.get('payment_method')
            logger.info(f"Product Name: {product_name}, Name: {name}, Shipping Address: {shipping_address}, Payment Method: {payment_method}")
            if product_name and name and shipping_address and payment_method and not any(['?' in param for param in (product_name, name, shipping_address, payment_method)]):
                order_confirmation = place_order(product_name, quantity, shipping_address, payment_method, name)
                responseBody = {'TEXT': {'body': order_confirmation}} if order_confirmation else {'TEXT': {'body': 'Error placing order. Please try again later.'}}
            else:
                responseBody = {'TEXT': {'body': "Name, shipping address, product name and payment method are required information."}}
    else:
        responseBody = {'TEXT': {'body': "Invalid actionGroup or function"}}

    action_response = {
        'actionGroup': actionGroup,
        'function': function,
        'functionResponse': {
            'responseBody': responseBody
        }
    }

    function_response = {'response': action_response, 'messageVersion': event['messageVersion']}
    logger.info("Response: {}".format(function_response))

    return function_response

# (Optional) Test event for local testing
if __name__ == "__main__":
    test_place_order_event = {
        "messageVersion": "1.0",
        "agent": {
            "name": "customer-support-agent",
            "version": "DRAFT",
            "id": "OYRAG4B01F",
            "alias": "TSTALIASID"
        },
        "function": "place-order",
        "parameters": [
            {
                "name": "product_name",
                "type": "string",
                "value": "A100 SmartWatch"
            },
            {
                "name": "name",
                "type": "string",
                "value": "John Doe"
            },
            {
                "name": "quantity",
                "type": "string",
                "value": "1"
            },
            {
                "name": "shipping_address",
                "type": "string",
                "value": "123 Main St, Anytown USA"
            },
            {
                "name": "payment_method",
                "type": "string",
                "value": "Credit Card"
            }
        ],
        "sessionId": "",
        "sessionAttributes": {},
        "promptSessionAttributes": {},
        "actionGroup": "order-action-group"
    }
    result = lambda_handler(test_place_order_event, None)
    print("Response: {}".format(result))
    
    
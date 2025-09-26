
import json
import logging
from datetime import datetime

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

orders_db = {
    "ORD12345": {
        "order_id": "ORD12345",
        "customer_name": "John Doe",
        "product_id": "PROD123",
        "item": "wireless headphones",
        "status": "Out for delivery",
        "delivery_date": "2024-04-10",
        "order_history": [
            {"timestamp": "2024-03-01T12:00:00", "event": "Order Placed"},
            {"timestamp": "2024-03-03T09:30:00", "event": "Order Shipped"},
            {"timestamp": "2024-04-10T15:45:00", "event": "Out for Delivery"}
        ]
    },
    "ORD67890": {
        "order_id": "ORD67890",
        "customer_name": "Jane Smith",
        "product_id": "PROD456",
        "item": "smart watch",
        "status": "Processing",
        "delivery_date": "2024-03-15",
        "order_history": [
            {"timestamp": "2024-03-02T10:30:00", "event": "Order Placed"}
        ]
    },
    "ORD11111": {
        "order_id": "ORD11111",
        "customer_name": "Rohit Kumar",
        "product_id": "PROD789",
        "item": "laptop",
        "status": "Delivered",
        "delivery_date": "2024-05-08",
        "order_history": [
            {"timestamp": "2024-04-05T08:00:00", "event": "Order Placed"},
            {"timestamp": "2024-04-07T14:20:00", "event": "Order Shipped"},
            {"timestamp": "2024-05-08T10:15:00", "event": "Delivered"}
        ]
    }
}


def get_order_details(order_id):
    """
    Fetch details of a customer order, including tracking info and order history. In the real world application, you will get this data from a database.
    """
    return orders_db.get(order_id)

def cancel_order(order_id):
    """
    Cancel a customer order and update the order history. In practice, you will update your system instead.
    """
    orders_db[order_id]["status"] = "Cancelled"
    orders_db[order_id]["order_history"].append({"timestamp": get_current_timestamp(), "event": "Order Cancelled"})
    return {"message": f"Order {order_id} has been cancelled."}

def get_current_timestamp():
    """
    Get the current timestamp in the desired format.
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

# Primary Handler 
def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))
    
    # Extract parameters from the event
    agent = event['agent']
    actionGroup = event['actionGroup']
    function = event['function']
    parameters = {param['name']: param['value'] for param in event.get('parameters', [])}

    # Validate the required parameter
    order_id = parameters.get('order_id')
    if order_id not in orders_db:
        responseBody = {'TEXT': {'body': f"No order found with ID {order_id}"}}

    if actionGroup == 'order-action-group':
        if function == 'retrieve-order-tracking-info':
            responseBody = {'TEXT': {'body': json.dumps(get_order_details(order_id))}}
        elif function == 'cancel-order':
            responseBody = {'TEXT': {'body': cancel_order(order_id)['message']}}
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
    test_event = {
        "messageVersion": "1.0",
        "agent": {
        "name": "customer-support-agent",
        "version": "DRAFT",
        "id": "OYRAG4B01F",
        "alias": "TSTALIASID"
        },
        "function": "cancel-order",
        "parameters": [
        {
            "name": "order_id",
            "type": "string",
            "value": "ORD11111"
        }
        ],
        "sessionId": "",
        "sessionAttributes": {},
        "promptSessionAttributes": {},
        "actionGroup": "order-action-group"
    }
    result = lambda_handler(test_event, None)
    print("Response: {}".format(result))
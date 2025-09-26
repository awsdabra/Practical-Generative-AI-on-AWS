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
        "item": "laptop",
        "status": "Delivered",
        "delivery_date": "2024-05-08",
        "order_history": [
            {"timestamp": "2024-04-05T08:00:00", "event": "Order Placed"},
            {"timestamp": "2024-04-07T14:20:00", "event": "Order Shipped"},
            {"timestamp": "2024-05-08T10:15:00", "event": "Delivered"}
        ]
    },
    "ORD99999": {
        "order_id": "ORD99999",
        "customer_name": "Maya Singh",
        "item": "smart tv",
        "status": "Return Initiated",
        "delivery_date": "2024-06-07",
        "order_history": [
            {"timestamp": "2024-05-30T08:00:00", "event": "Order Placed"},
            {"timestamp": "2024-06-01T14:20:00", "event": "Order Shipped"},
            {"timestamp": "2024-06-07T10:15:00", "event": "Delivered"},
            {"timestamp": "2024-06-10T10:05:00", "event": "Return Initiated"}
        ]
    }
}


def initiate_return(order_id, reason):
    """
    Process a return request for a customer order and update the order history. In practice, you will update the database or call system apis
    """
    order = orders_db.get(order_id)
    if order:
        if order["status"] == "Delivered":
            order["status"] = "Return Initiated"
            order["order_history"].append({
                "timestamp": get_current_timestamp(),
                "event": f"Return Initiated: {reason}"
            })
            item_name = order["item"]
            return {"message": f"Return initiated for order {order_id}({item_name}). Please ship the item back within 30 days."}
        else:
            return {"message": f"Unable to initiate return for order {order_id} as it has not been delivered yet."}
    else:
        return {"message": f"No order found with ID {order_id}"}

def process_refund(order_id):
    """
    Process a refund request for a customer order and update the order history.
    """
    order = orders_db.get(order_id)
    if order:
        if order["status"] == "Return Initiated":
            order["status"] = "Refunded"
            order["order_history"].append({
                "timestamp": get_current_timestamp(),
                "event": "Order Refunded"
            })
            item_name = order["item"]
            return {"message": f"Refund processed for order {order_id} ({item_name})."}
        else:
            return {"message": f"Unable to process refund for order {order_id} as the return has not been initiated."}
    else:
        return {"message": f"No order found with ID {order_id}"}

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

    if actionGroup == 'return-refund-action-group':
        if function == 'initiate-return':
            reason = parameters.get('reason')
            responseBody = {'TEXT': {'body': initiate_return(order_id, reason)['message']}}
        elif function == 'process-refund':
            responseBody = {'TEXT': {'body': process_refund(order_id)['message']}}
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
        "alias": "TSTALIASID"
        },
        "actionGroup": "return-refund-action-group",
        "function": "initiate-return",
        "parameters": [
        {
            "name": "order_id",
            "type": "string",
            "value": "ORD11111"
        },
        {
            "name": "reason",
            "type": "string",
            "value": "Item damaged"
        }
        ]
    }
    result = lambda_handler(test_event, None)
    print("Response: {}".format(result))
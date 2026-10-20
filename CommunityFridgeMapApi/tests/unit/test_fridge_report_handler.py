import unittest

import pytest
import base64

from CommunityFridgeMapApi.functions.fridge_reports.app import FridgReportHandler
import json


class DynamoDbMockPutItem:
    def __init__(self):
        self.query_parameters = None

    def put_item(self, TableName=None, Item=None, ConditionExpression=None):
        pass

    def get_item(self, TableName=None, Key=None):
        return {"Item": {"json_data": {"S": '{"id": {"S": "test"}}'}}}

    def update_item(
        self,
        TableName=None,
        Key=None,
        ExpressionAttributeNames=None,
        ExpressionAttributeValues=None,
        UpdateExpression=None,
    ):
        pass

    def query(self, **kwargs):
        self.query_parameters = kwargs
        return {
            "Items": [
                {"json_data": {"S": '{"fridgeId": "thefriendlyfridge", "condition": "good"}'}}
            ],
            "LastEvaluatedKey": {
                "fridgeId": {"S": "thefriendlyfridge"},
                "epochTimestamp": {"N": "123"},
            },
        }


class FrdgeReportHandlerTest(unittest.TestCase):
    def test_lambda_handler_success(self):
        event = {
            "body": '{"condition": "good", "foodPercentage": 2}',
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
            "httpMethod": "POST",
        }
        response = FridgReportHandler.lambda_handler(
            event=event, ddbclient=DynamoDbMockPutItem()
        )
        self.assertEqual(response["statusCode"], 201)
        body = json.loads(response["body"])
        self.assertEqual(body["fridgeId"], "thefriendlyfridge")
        self.assertTrue("timestamp" in body)

    def test_get_fridge_report_history_returns_page_and_cursor(self):
        event = {
            "resource": "/v1/fridges/{fridgeId}/reports/history",
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
            "queryStringParameters": None,
            "httpMethod": "GET",
        }
        ddb_client = DynamoDbMockPutItem()

        response = FridgReportHandler.lambda_handler(event, ddb_client)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(len(body["reports"]), 1)
        self.assertEqual(ddb_client.query_parameters["Limit"], 5)
        self.assertFalse(ddb_client.query_parameters["ScanIndexForward"])
        self.assertIsNotNone(body["nextToken"])

    def test_get_fridge_report_history_uses_cursor(self):
        cursor = {
            "fridgeId": {"S": "thefriendlyfridge"},
            "epochTimestamp": {"N": "123"},
        }
        next_token = base64.urlsafe_b64encode(json.dumps(cursor).encode()).decode()
        event = {
            "resource": "/v1/fridges/{fridgeId}/reports/history",
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
            "queryStringParameters": {"nextToken": next_token},
            "httpMethod": "GET",
        }
        ddb_client = DynamoDbMockPutItem()

        FridgReportHandler.lambda_handler(event, ddb_client)

        self.assertEqual(ddb_client.query_parameters["ExclusiveStartKey"], cursor)

    def test_get_fridge_report_history_rejects_invalid_cursor(self):
        event = {
            "resource": "/v1/fridges/{fridgeId}/reports/history",
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
            "queryStringParameters": {"nextToken": "not-a-valid-token"},
            "httpMethod": "GET",
        }

        response = FridgReportHandler.lambda_handler(event, DynamoDbMockPutItem())

        self.assertEqual(response["statusCode"], 400)

    def test_lambda_handler_fail(self):
        event = {
            "body": '{"condition": "good"}',
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
            "httpMethod": "POST",
        }
        response = FridgReportHandler.lambda_handler(
            event=event, ddbclient=DynamoDbMockPutItem()
        )
        self.assertEqual(response["statusCode"], 400)
        message = json.loads(response["body"])["message"]
        self.assertEqual(message, "Missing Required Field: foodPercentage")

    def test_lambda_handler_exception(self):
        event = {
            "body": '{"condition": "good", "foodPercentage": 2}',
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
        }
        response = FridgReportHandler.lambda_handler(
            event=event, ddbclient=DynamoDbMockPutItem()
        )
        self.assertEqual(response["statusCode"], 400)
        message = json.loads(response["body"])["message"]
        self.assertEqual(message, "httpMethod missing")

    def test_lambda_handler_with_user_id(self):
        event = {
            "body": '{"condition": "good", "foodPercentage": 2, "userId": "user_abc123"}',
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
            "httpMethod": "POST",
        }
        response = FridgReportHandler.lambda_handler(
            event=event, ddbclient=DynamoDbMockPutItem()
        )
        self.assertEqual(response["statusCode"], 201)
        body = json.loads(response["body"])
        self.assertEqual(body["fridgeId"], "thefriendlyfridge")
        self.assertTrue("timestamp" in body)

    def test_lambda_handler_without_user_id(self):
        event = {
            "body": '{"condition": "good", "foodPercentage": 2}',
            "pathParameters": {"fridgeId": "thefriendlyfridge"},
            "httpMethod": "POST",
        }
        response = FridgReportHandler.lambda_handler(
            event=event, ddbclient=DynamoDbMockPutItem()
        )
        self.assertEqual(response["statusCode"], 201)

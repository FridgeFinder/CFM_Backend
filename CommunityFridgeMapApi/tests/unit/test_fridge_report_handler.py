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

class DynamoDbMockDeleteReport:
    def __init__(self, latest_report, remaining_reports=None, report_exists=True):
        self.fridge_json = json.dumps(
            {"id": "thefriendlyfridge", "latestFridgeReport": latest_report}
        )
        self.remaining_reports = remaining_reports or []
        self.report_exists = report_exists
        self.delete_parameters = None
        self.query_parameters = None
        self.update_parameters = None

    def get_item(self, TableName=None, Key=None):
        return {"Item": {"json_data": {"S": self.fridge_json}}}

    def delete_item(self, **kwargs):
        self.delete_parameters = kwargs
        if self.report_exists:
            return {"Attributes": {"json_data": {"S": "{}"}}}
        return {}

    def query(self, **kwargs):
        self.query_parameters = kwargs
        return {
            "Items": [
                {"json_data": {"S": json.dumps(report)}}
                for report in self.remaining_reports
            ]
        }

    def update_item(self, **kwargs):
        self.update_parameters = kwargs

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

    def test_delete_newest_report_updates_fridge_to_previous_report(self):
        previous_report = {"fridgeId": "thefriendlyfridge", "epochTimestamp": "199"}
        ddb_client = DynamoDbMockDeleteReport(
            latest_report={"fridgeId": "thefriendlyfridge", "epochTimestamp": "200"},
            remaining_reports=[previous_report],
        )
        event = {
            "pathParameters": {
                "fridgeId": "thefriendlyfridge",
                "epochTimestamp": "200",
            },
            "httpMethod": "DELETE",
        }

        response = FridgReportHandler.lambda_handler(event, ddb_client)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            ddb_client.delete_parameters["Key"],
            {
                "fridgeId": {"S": "thefriendlyfridge"},
                "epochTimestamp": {"N": "200"},
            },
        )
        self.assertEqual(ddb_client.query_parameters["Limit"], 1)
        self.assertFalse(ddb_client.query_parameters["ScanIndexForward"])
        self.assertEqual(
            json.loads(
                ddb_client.update_parameters["ExpressionAttributeValues"][":fr"]["S"]
            ),
            previous_report,
        )

    def test_delete_non_newest_report_does_not_update_fridge(self):
        ddb_client = DynamoDbMockDeleteReport(
            latest_report={"fridgeId": "thefriendlyfridge", "epochTimestamp": "200"}
        )
        event = {
            "pathParameters": {
                "fridgeId": "thefriendlyfridge",
                "epochTimestamp": "199",
            },
            "httpMethod": "DELETE",
        }

        response = FridgReportHandler.lambda_handler(event, ddb_client)

        self.assertEqual(response["statusCode"], 200)
        self.assertIsNone(ddb_client.query_parameters)
        self.assertIsNone(ddb_client.update_parameters)

    def test_delete_last_report_clears_latest_fridge_report(self):
        ddb_client = DynamoDbMockDeleteReport(
            latest_report={"fridgeId": "thefriendlyfridge", "epochTimestamp": "200"}
        )
        event = {
            "pathParameters": {
                "fridgeId": "thefriendlyfridge",
                "epochTimestamp": "200",
            },
            "httpMethod": "DELETE",
        }

        response = FridgReportHandler.lambda_handler(event, ddb_client)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            ddb_client.update_parameters["UpdateExpression"], "SET #JD = :fj REMOVE #LFR"
        )
        updated_fridge = json.loads(
            ddb_client.update_parameters["ExpressionAttributeValues"][":fj"]["S"]
        )
        self.assertNotIn("latestFridgeReport", updated_fridge)

    def test_delete_report_returns_not_found_when_report_does_not_exist(self):
        ddb_client = DynamoDbMockDeleteReport(
            latest_report={"fridgeId": "thefriendlyfridge", "epochTimestamp": "200"},
            report_exists=False,
        )
        event = {
            "pathParameters": {
                "fridgeId": "thefriendlyfridge",
                "epochTimestamp": "199",
            },
            "httpMethod": "DELETE",
        }

        response = FridgReportHandler.lambda_handler(event, ddb_client)

        self.assertEqual(response["statusCode"], 404)
        self.assertIsNone(ddb_client.query_parameters)

    def test_delete_report_rejects_invalid_epoch_timestamp(self):
        ddb_client = DynamoDbMockDeleteReport(
            latest_report={"fridgeId": "thefriendlyfridge", "epochTimestamp": "200"}
        )
        event = {
            "pathParameters": {
                "fridgeId": "thefriendlyfridge",
                "epochTimestamp": "not-a-timestamp",
            },
            "httpMethod": "DELETE",
        }

        response = FridgReportHandler.lambda_handler(event, ddb_client)

        self.assertEqual(response["statusCode"], 400)
        self.assertIsNone(ddb_client.delete_parameters)

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

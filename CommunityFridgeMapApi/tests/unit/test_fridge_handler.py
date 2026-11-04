import json

from CommunityFridgeMapApi.functions.fridges.v1.app import FridgeHandler
from dependencies.python.db import layer_test
from dependencies.python.db import get_ddb_connection
import unittest


class DynamoDbMockGetItem:
    def __init__(self):
        pass

    def get_item(self, TableName=None, Key=None):
        return {"Item": {"json_data": {"S": '{"id": {"S": "test"}}'}}}
    
class DynamoDbMockGetItemFail:
    def __init__(self):
        pass

    def get_item(self, TableName=None, Key=None):
        return {} 


class DynamoDbMockScan:
    def __init__(self):
        pass

    def scan(
        self,
        TableName=None,
        FilterExpression=None,
        ExpressionAttributeValues=None,
        ProjectionExpression=None,
    ):
        return {"Items": [{"json_data": {"S": '{"id": {"S": "test"}}'}}]}


class DynamoDbMockPatch:
    def __init__(self, fridge=None):
        self.fridge = fridge or {
            "id": "test",
            "name": "Test Fridge",
            "location": {"geoLat": "40.7", "geoLng": "-73.9"},
            "notes": "Original notes",
        }
        self.update_call = None

    def get_item(self, TableName=None, Key=None):
        return {"Item": {"json_data": {"S": json.dumps(self.fridge)}}}

    def update_item(self, **kwargs):
        self.update_call = kwargs


class FridgeHandlerTest(unittest.TestCase):
    def test_get_item_success(self):
        json_data = '{"id": {"S": "test"}}'
        response = FridgeHandler.lambda_handler(
            event={
                "httpMethod": "GET",
                "pathParameters": {"fridgeId": "test"},
                "queryStringParameters": None,
            },
            ddbclient=DynamoDbMockGetItem(),
        )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["body"], json_data)

    def test_patch_updates_fridge_fields(self):
        ddbclient = DynamoDbMockPatch()
        response = FridgeHandler.lambda_handler(
            event={
                "httpMethod": "PATCH",
                "pathParameters": {"fridgeId": "test"},
                "body": (
                    '{"name": "Updated Fridge", '
                    '"location": {"geoLat": "40.8", "geoLng": "-73.8"}, '
                    '"maintainer": {"name": "Fridge Keeper"}, '
                    '"notes": "New notes", '
                    '"photoUrl": "https://example.com/fridge.jpg"}'
                ),
            },
            ddbclient=ddbclient,
        )

        self.assertEqual(response["statusCode"], 200)
        updated_fridge = json.loads(response["body"])
        self.assertEqual(updated_fridge["name"], "Updated Fridge")
        self.assertEqual(
            updated_fridge["location"],
            {"geoLat": "40.8", "geoLng": "-73.8"},
        )
        self.assertEqual(
            updated_fridge["maintainer"], {"name": "Fridge Keeper"}
        )
        self.assertEqual(updated_fridge["notes"], "New notes")
        self.assertEqual(
            updated_fridge["photoUrl"], "https://example.com/fridge.jpg"
        )
        self.assertIn("last_edited", updated_fridge)
        self.assertIn("SET", ddbclient.update_call["UpdateExpression"])
        self.assertEqual(
            json.loads(
                ddbclient.update_call["ExpressionAttributeValues"][":json_data"]["S"]
            ),
            updated_fridge,
        )

    def test_patch_rejects_fields_outside_allowlist(self):
        ddbclient = DynamoDbMockPatch()
        response = FridgeHandler.lambda_handler(
            event={
                "httpMethod": "PATCH",
                "pathParameters": {"fridgeId": "test"},
                "body": '{"id": "another-id"}',
            },
            ddbclient=ddbclient,
        )

        self.assertEqual(response["statusCode"], 400)
        self.assertIsNone(ddbclient.update_call)

    def test_patch_rejects_malformed_json(self):
        response = FridgeHandler.lambda_handler(
            event={
                "httpMethod": "PATCH",
                "pathParameters": {"fridgeId": "test"},
                "body": "{",
            },
            ddbclient=DynamoDbMockPatch(),
        )

        self.assertEqual(response["statusCode"], 400)

    def test_get_item_failure(self):
        response = FridgeHandler.lambda_handler(
            event={
                "httpMethod": "GET",
                "pathParameters": {"fridgeId": "hi"},
                "queryStringParameters": None,
            },
            ddbclient=DynamoDbMockGetItemFail(),
        )
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(
            response["body"],
            '{"message": "Fridge was not found"}',
        )

    def test_get_items(self):
        json_data = '[{"id": {"S": "test"}}]'
        response = FridgeHandler.lambda_handler(
            event={
                "httpMethod": "GET",
                "pathParameters": None,
                "queryStringParameters": None,
            },
            ddbclient=DynamoDbMockScan(),
        )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["body"], json_data)

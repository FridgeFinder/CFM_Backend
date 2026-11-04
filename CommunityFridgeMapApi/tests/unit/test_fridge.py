import pytest
from CommunityFridgeMapApi.dependencies.python.db import FridgeReport
from CommunityFridgeMapApi.functions.fridges.v1.app import FridgeHandler
from dependencies.python.db import layer_test
from dependencies.python.db import get_ddb_connection
import unittest
from dependencies.python.db import Fridge
import json
import os


def test_layer_test():

    ret = layer_test()
    assert ret == "hello world"


def test_get_ddb_connection():
    os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
    connection = get_ddb_connection()
    assert str(type(connection)) == "<class 'botocore.client.DynamoDB'>"
    connection = get_ddb_connection(env="local")
    assert str(type(connection)) == "<class 'botocore.client.DynamoDB'>"


class DynamoDbMockPutItem:
    def __init__(self):
        pass

    def put_item(self, TableName=None, Item=None, ConditionExpression=None):
        pass


class DynamoDbMockPutItem_HashCollision:
    def __init__(self):
        # Mock the exceptions attribute that DynamoDB client has
        self.exceptions = type('Exceptions', (), {
            'ConditionalCheckFailedException': type('ConditionalCheckFailedException', (Exception,), {})
        })()

    def put_item(self, TableName=None, Item=None, ConditionExpression=None):
        # Always raise ConditionalCheckFailedException to simulate hash collision
        raise self.exceptions.ConditionalCheckFailedException("Conditional check failed")


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


class FridgeTest(unittest.TestCase):
    def test_set_id(self):
        fridge = Fridge(fridge={}, db_client=None)
        fridge.set_id()
        self.assertIsNotNone(fridge.id)
        self.assertEqual(len(fridge.id), fridge.HASH_ID_LENGTH)

    def test_set_id_removes_ampersand(self):
        fridge = Fridge(fridge={"name": "Food & Friends"}, db_client=None)
        fridge.set_id()
        self.assertEqual(fridge.id, "foodfriends")

    def test_set_last_edditted(self):
        fridge = Fridge(fridge={"name": "The Friendly Fridge"}, db_client=None)
        self.assertIsNone(fridge.last_edited)
        fridge.set_last_edited()
        self.assertIsNotNone(fridge.last_edited)


    def test_add_item_missing_required_field(self):
        db_client = DynamoDbMockPutItem()
        fridge = Fridge(
            fridge={
                "name": "test fridge",
                "location": {"geoLat": 12124},
            },
            db_client=db_client,
        )
        response = fridge.add_item()
        self.assertFalse(response.success)
        self.assertEqual(response.message, "Missing Required Field: location/geoLng")
        self.assertEqual(response.status_code, 400)

    def test_add_item_min_length_failure(self):
        db_client = DynamoDbMockPutItem()
        fridge = Fridge(
            fridge={
                "name": "it",
                "location": {"geoLat": 12124, "geoLng": 232523},
            },
            db_client=db_client,
        )
        response = fridge.add_item()
        self.assertFalse(response.success)
        self.assertEqual(response.message, "name character length must be >= 3")
        self.assertEqual(response.status_code, 400)

    def test_add_item_success(self):
        db_client = DynamoDbMockPutItem()
        fridge = Fridge(
            fridge={
                "location": {"geoLat": 124242, "geoLng": 2345235},
            },
            db_client=db_client,
        )
        response = fridge.add_item()
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(fridge.last_edited)
        # Parse the JSON response to verify the HASHED ID was generated
        response_data = json.loads(response.json_data)
        self.assertIn("id", response_data)
        self.assertEqual(len(response_data["id"]), fridge.HASH_ID_LENGTH)

    def test_format_dynamodb_item_v2(self):
        fridge = {
            "name": "test",
            "id": "test",
            "tags": ["tag3"],
            "location": {},
            "maintainer": {},
            "notes": "test",
            "food_accepts": ["dairy"],
            "food_restrictions": ["meat"],
            "photoUrl": "test",
            "last_edited": 2342353,
            "verified": True,
            "latestFridgeReport": {},
        }
        fridge_item = Fridge(fridge=fridge, db_client=None).format_dynamodb_item_v2()
        expected_response = {
            "name": {"S": "test"},
            "id": {"S": "test"},
            "tags": {"L": [{"S": "tag3"}]},
            "location": {"S": "{}"},
            "maintainer": {"S": "{}"},
            "notes": {"S": "test"},
            "food_accepts": {"L": [{"S": "dairy"}]},
            "food_restrictions": {"L": [{"S": "meat"}]},
            "photoUrl": {"S": "test"},
            "last_edited": {"N": "2342353"},
            "verified": {"BOOL": True},
            "latestFridgeReport": {"S": "{}"},
            "json_data": {"S": json.dumps(fridge)},
        }
        self.assertEqual(fridge_item, expected_response)
        fridge_item = Fridge(
            fridge={"id": ""}, db_client=None
        ).format_dynamodb_item_v2()
        self.assertEqual(fridge_item, {"json_data": {"S": "{}"}})

    def test_validate_fields_required_fields(self):
        fridge = Fridge(fridge={}, db_client=None)
        field_validator = fridge.validate_fields()
        self.assertFalse(field_validator.is_valid)
        self.assertEqual(field_validator.message, "Missing Required Field: id")

    def test_validate_fields_min_length(self):
        fridge = Fridge(fridge={"id": "x"}, db_client=None)
        field_validator = fridge.validate_fields()
        self.assertFalse(field_validator.is_valid)
        self.assertEqual(field_validator.message, "id character length must be >= 3")

    def test_validate_fields_max_length(self):
        fridge = Fridge(
            fridge={
                "id": "x" * 101,
                "name": "x" * 101,
                "location": {"geoLat": "3", "geoLng": "3"},
            },
            db_client=None,
        )
        field_validator = fridge.validate_fields()
        self.assertFalse(field_validator.is_valid)
        self.assertEqual(field_validator.message, "id character length must be <= 100")

    def test_validate_fields_success(self):
        fridge = Fridge(
            fridge={
                "id": "goodAZaz09_#-‘'.",
                "name": "goodAZaz09_#-‘'. ",
                "location": {"geoLat": 232342, "geoLng": 2342342},
            },
            db_client=None,
        )
        field_validator = fridge.validate_fields()
        self.assertTrue(field_validator.is_valid)
        self.assertEqual(
            field_validator.message, "All Fields Were Successfully Validated"
        )

    def test_get_items(self):
        response = Fridge(db_client=DynamoDbMockScan()).get_items()
        expected_response = '[{"id": {"S": "test"}}]'
        self.assertTrue(response.is_successful())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json_data, expected_response)

    def test_get_items_tag(self):
        response = Fridge(db_client=DynamoDbMockScan()).get_items(tag="tag_test")
        expected_response = '[{"id": {"S": "test"}}]'
        self.assertTrue(response.is_successful())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json_data, expected_response)

    def test_add_item_hash_collision_fallback(self):
        # Mock client always fails condition checks
        mock_client = DynamoDbMockPutItem_HashCollision()
        fridge_item = Fridge(
            fridge={
                "name": "Test Fridge",
                "location": {"geoLat": 124242, "geoLng": 2345235},
            },
            db_client=mock_client,
        )
        
        # this should exhaust all retries and return the fallback response
        result = fridge_item.add_item()
        
        # Assert the fallback behavior
        assert result.success == False
        assert result.status_code == 500
        assert "Unable to generate unique fridge ID after" in result.message
        assert str(fridge_item.HASH_COLLISION_RETRIES) in result.message

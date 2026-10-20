import os
import boto3
import base64
import time
import re
import json
import logging
import datetime
import secrets
import string
from typing import Tuple
from dataclasses import dataclass
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_ddb_connection(
    env: str = os.getenv("Environment", "")
) -> "botocore.client.DynamoDB":
    ddbclient = ""
    if env == "local":
        ddbclient = boto3.client("dynamodb", endpoint_url="http://localstack:4566/")
    else:
        ddbclient = boto3.client("dynamodb")
    return ddbclient


def layer_test() -> str:
    return "hello world"


@dataclass
class Field_Validator:
    is_valid: str
    message: str


class DB_Response:
    def __init__(
        self, success: bool, status_code: int, message: str, json_data: str = None):
        self.message = message
        self.status_code = status_code
        self.success = success
        self.json_data = json_data

    def is_successful(self) -> bool:
        return self.success

    def get_dict_form(self) -> dict:
        return {
            "messsage": self.message,
            "success": self.success,
            "status_code": self.status_code,
            "json_data": self.json_data,
        }

    def set_json_data(self, json_data: str):
        self.json_data = json_data

    def api_format(self) -> dict:
        if self.json_data:
            body = self.json_data
        else:
            body = json.dumps({"message": self.message})
        return {
            "statusCode": self.status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": (body),
        }


class DB_Item:

    REQUIRED_FIELDS = []
    ITEM_TYPES = {}
    TABLE_NAME = ""
    FIELD_VALIDATION = {}
    STAGE = os.getenv("Stage", "")

    def __init__(self, db_client: "botocore.client.DynamoDB"):
        self.db_client = db_client
        pass

    def add_item(self, conditional_expression=None) -> DB_Response:
        """
        adds item to database
            Parameters:
                conditional_expression (str): conditional expression for boto3 function put_item

            Returns:
                db_response (DB_Response): returns a DB_Response
        """
        field_validation = self.validate_fields()
        if not field_validation.is_valid:
            return DB_Response(
                message=field_validation.message, status_code=400, success=False
            )
        item = self.format_dynamodb_item_v2()
        try:
            if conditional_expression:
                self.db_client.put_item(
                    TableName=self.TABLE_NAME,
                    Item=item,
                    ConditionExpression=conditional_expression,
                )
            else:
                self.db_client.put_item(TableName=self.TABLE_NAME, Item=item)
        except self.db_client.exceptions.ConditionalCheckFailedException as e:
            return DB_Response(
                message=f"Conditional check failed for table: {self.TABLE_NAME}, condition: {conditional_expression}",
                status_code=409,
                success=False,
            )
        except self.db_client.exceptions.ResourceNotFoundException as e:
            message = f"Cannot do operations on a non-existent table: {self.TABLE_NAME}"
            logging.error(message)
            return DB_Response(message=message, status_code=500, success=False)
        except ClientError as e:
            logging.error(e)
            return DB_Response(
                message="Unexpected AWS service exception",
                status_code=500,
                success=False,
            )
        return DB_Response(
            message=f"{self.TABLE_NAME} was succesfully added",
            status_code=201,
            success=True,
        )

    def update_item(self):
        pass

    def get_item(self, primary_key):
        pass

    def delete_item(self):
        pass

    def get_all_items(self):
        """
        Gets all the Fridge Items
        NOTE: This function is probably fine for the fridges in NYC. But as more fridges
        are added to the database, this will be a bottleneck. Ideally we would be querying
        based on proximity. Here is an option for if we ever need to transition:
        https://hometechtime.com/how-to-build-a-dynamodb-geo-database-to-store-and-query-geospatial-data/
        TODO: paginate? 
        """
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.scan
        return self.db_client.scan(TableName=self.TABLE_NAME)

    def has_required_fields(self) -> tuple:
        for field in self.REQUIRED_FIELDS:
            if getattr(self, field) is None:
                return (False, field)
        return (True, None)

    def get_class_field_value(self, key: str):
        """
        Gets the class field value based on a key.
        The parameter key can be the class field name or in the case of a dictionary can contain "/"
        "/" is used when a class field is a dictionary and the client wants to get the value of a child field
        Example: location: {geoLng: 23.4323}
                 key = "location/geoLng"
        In order to get the value of geoLng the client would use the key "location/geoLng"
            Parameters:
                key (str): the name of the class field the client wants to obtain the value of

            Returns:
                object_dict (dict): the class field value
        """
        class_field_value = None
        if "/" in key:
            key_split = key.split("/")
            parent_key = key_split[0]
            class_field_value = getattr(self, parent_key)
            for i in range(1, len(key_split)):
                if class_field_value is None:
                    break
                child_key = key_split[i]
                class_field_value = class_field_value.get(child_key, None)
        else:
            class_field_value = getattr(self, key)
        return class_field_value

    def format_dynamodb_item_v2(self):
        """
        Creates a dictionary in the syntax that dynamodb expects
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.put_item
        """
        fridge_item = {}
        fridge_json = {}
        for key in self.FIELD_VALIDATION:
            if "/" in key:
                continue
            val = getattr(self, key)
            if val is not None:
                fridge_json[key] = val
                if isinstance(val, int) and not isinstance(val, bool):
                    val = str(val)
                if isinstance(val, dict):
                    val = json.dumps(val)
                elif isinstance(val, list):
                    fridge_json[key] = val.copy()
                    list_type = self.FIELD_VALIDATION[key]["list_type"]
                    val = val.copy()
                    for index, v in enumerate(val):
                        val[index] = {list_type: v}
                fridge_item[key] = {self.FIELD_VALIDATION[key]["type"]: val}
        fridge_item["json_data"] = {"S": json.dumps(fridge_json)}
        return fridge_item

    @staticmethod
    def process_fields(object_dict: dict) -> dict:
        """
        Removes extra white spaces, trailing spaces, leading spaces from object_dict values
        If the length of the field is ZERO after removing the white spaces, sets the value to None
            Parameters:
                object_dict (dict): a dictinary

            Returns:
                object_dict (dict):
        """
        for key, value in object_dict.items():
            if isinstance(value, str):
                object_dict[key] = DB_Item.remove_extra_whitespace(value)
            if isinstance(value, dict):
                object_dict[key] = DB_Item.process_fields(value)
            if isinstance(value, list):
                for index, val in enumerate(value):
                    if isinstance(val, str):
                        value[index] = DB_Item.remove_extra_whitespace(val)
        return object_dict

    @staticmethod
    def remove_extra_whitespace(value: str):
        """
        Removes extra white spaces, trailing spaces, and leading spaces
        Example: Input: " hi    there " Output: "hi there"
            Parameters:
                value (str): a string
            Returns:
                value (str): the value parameter without extra white spaces,
                             trailing spaces, and leading spaces
        """
        value = re.sub(" +", " ", value).strip()
        if len(value) == 0:
            value = None
        return value

    def validate_fields(self) -> Field_Validator:
        """
        Validates that all the fields are valid.
        All fields are valid if they pass all the constraints set in FIELD_VALIDATION
        """
        for key, field_validation in self.FIELD_VALIDATION.items():
            class_field_value = self.get_class_field_value(key)
            is_not_none = class_field_value is not None
            required = field_validation.get("required", None)
            min_length = field_validation.get("min_length", None)
            max_length = field_validation.get("max_length", None)
            choices = field_validation.get("choices", None)
            if required:
                if class_field_value is None:
                    return Field_Validator(
                        is_valid=False, message=f"Missing Required Field: {key}"
                    )
            if min_length and is_not_none:
                if len(str(class_field_value)) < min_length:
                    return Field_Validator(
                        is_valid=False,
                        message=f"{key} character length must be >= {min_length}",
                    )
            if max_length and is_not_none:
                if len(str(class_field_value)) > max_length:
                    return Field_Validator(
                        is_valid=False,
                        message=f"{key} character length must be <= {max_length}",
                    )
            if choices and is_not_none:
                if class_field_value not in choices:
                    return Field_Validator(
                        is_valid=False,
                        message=f"{key} must to be one of: {str(choices)}",
                    )
        return Field_Validator(
            is_valid=True, message="All Fields Were Successfully Validated"
        )

    def warm_lambda(self):
        key = {"id": {"S": "collectivefocusresourcehub"}}
        self.db_client.get_item(TableName=self.TABLE_NAME, Key=key)


class Fridge(DB_Item):
    MIN_ID_LENGTH = 3
    MAX_ID_LENGTH = 100
    MAX_NAME_LENGTH = MAX_ID_LENGTH + 10
    HASH_COLLISION_RETRIES = 3
    HASH_ID_LENGTH = 6
    FIELD_VALIDATION = {
        "name": {
            "required": False,
            "min_length": MIN_ID_LENGTH,
            "max_length": MAX_NAME_LENGTH,
            "type": "S",
        },
        "id": {
            "required": True,
            "min_length": MIN_ID_LENGTH,
            "max_length": MAX_ID_LENGTH,
            "type": "S",
        },
        "tags": {"required": False, "type": "L", "list_type": "S"},
        "location": {"required": True, "type": "S"},
        "location/name": {"required": False, "max_length": 256},
        "location/street": {"required": False, "max_length": 256},
        "location/city": {"required": False, "max_length": 256},
        "location/state": {"required": False, "max_length": 256},
        "location/zip": {"required": False, "max_length": 10},
        "location/geoLat": {"required": True, "max_length": 20},
        "location/geoLng": {"required": True, "max_length": 20},
        "location/country": {"required": False, "max_length": 256},
        "maintainer": {"required": False, "type": "S"},
        "maintainer/name": {"required": False, "max_length": 256},
        "maintainer/organization": {"required": False, "max_length": 256},
        "maintainer/phone": {"required": False, "min_length": 10, "max_length": 20},
        "maintainer/email": {"required": False, "max_length": 320},
        "maintainer/website": {"required": False, "max_length": 2048},
        "maintainer/instagram": {"required": False, "max_length": 64},
        "notes": {"required": False, "max_length": 700, "type": "S"},
        "food_accepts": {"required": False, "type": "L", "list_type": "S"},
        "food_restrictions": {"required": False, "type": "L", "list_type": "S"},
        "photoUrl": {
            "required": False,
            "max_length": 2048,
            "type": "S",
        },
        "last_edited": {"required": False, "type": "N", "max_length": 20},
        "verified": {"required": False, "type": "BOOL"},
        "latestFridgeReport": {"required": False, "type": "S"},
        "latestFridgeReport/epochTimestamp": {"required": False},
        "latestFridgeReport/timestamp": {"required": False},
        "latestFridgeReport/condition": {"required": False},
        "latestFridgeReport/foodPercentage": {"required": False},
        "latestFridgeReport/photoUrl": {"required": False},
        "latestFridgeReport/notes": {"required": False},
        "latestFridgeReport/userId": {"required": False},
    }

    TABLE_NAME = f"fridge_{DB_Item.STAGE}"
    FOOD_ACCEPTS = []  # TODO: Fill this in
    FOOD_RESTRICTIONS = []  # TODO: fill this in

    def __init__(self, db_client: "botocore.client.DynamoDB", fridge: dict = None):
        super().__init__(db_client=db_client)
        if fridge is not None:
            fridge = DB_Item.process_fields(fridge)
            self.id: str = fridge.get("id", None)
            self.name: str = fridge.get("name", None)
            self.tags: list = fridge.get("tags", None)
            self.location: dict = fridge.get("location", None)
            self.maintainer: dict = fridge.get("maintainer", None)
            self.notes: str = fridge.get("notes", None)
            self.food_accepts: list = fridge.get("food_accepts", None)
            self.food_restrictions: list = fridge.get("food_restrictions", None)
            self.photoUrl: str = fridge.get("photoUrl", None)
            self.last_edited: str = fridge.get("last_edited", None)
            self.latestFridgeReport: dict = fridge.get("latestFridgeReport", None)
            self.verified: bool = fridge.get("verified", None)

    def get_item(self, fridgeId):
        key = {"id": {"S": fridgeId}}
        result = self.db_client.get_item(TableName=self.TABLE_NAME, Key=key)
        if "Item" not in result:
            return DB_Response(
                success=False, status_code=404, message="Fridge was not found"
            )
        else:
            json_data = result["Item"]["json_data"]["S"]
            return DB_Response(
                success=True,
                status_code=200,
                message="Successfully Found Fridge",
                json_data=json_data,
            )

    def get_latest_report(self, fridgeId):
        key = {"id": {"S": fridgeId}}
        result = self.db_client.get_item(TableName=self.TABLE_NAME, Key=key)
        if "Item" not in result:
            return DB_Response(
                success=False, status_code=404, message="Fridge was not found"
            )
        else:
            json_data = result["Item"]["json_data"]["S"]
            dict_data = json.loads(json_data)
            latestFridgeReport = dict_data.get("latestFridgeReport", None)
            response = []
            if latestFridgeReport is not None:
                response.append(latestFridgeReport)
            return DB_Response(
                success=True,
                status_code=200,
                message="Successfully Found Fridge",
                json_data=json.dumps(response),
            )

    def get_latest_fridge_reports(self):
        response = self.db_client.scan(TableName=self.TABLE_NAME)
        all_reports = []
        
        if "Items" in response:
            for item in response['Items']:
                json_data = item.get("json_data", {}).get("S", "{}")
                dict_data = json.loads(json_data)
                latestFridgeReport = dict_data.get("latestFridgeReport", None)
                if latestFridgeReport is not None:
                    all_reports.append(latestFridgeReport)
        
        return DB_Response(
            success=True,
            status_code=200,
            message="Successfully found fridge reports",
            json_data=json.dumps(all_reports),
        )
        

    def get_items(self, tag=None):
        # scan/query doc: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/dynamodb.html#querying-and-scanning
        response = None
        if tag:
            response = self.db_client.scan(
                TableName=self.TABLE_NAME,
                FilterExpression="contains (tags, :tag)",
                ExpressionAttributeValues={":tag": {"S": tag}},
                ProjectionExpression="json_data",
            )
        else:
            response = self.db_client.scan(
                TableName=self.TABLE_NAME, ProjectionExpression="json_data"
            )
        json_data_list = [item["json_data"]["S"] for item in response["Items"]]
        # Converts list of json to json.
        json_response = f"[{','.join(json_data_list)}]"
        return DB_Response(
            success=True,
            status_code=200,
            message="Query Successfully Completed",
            json_data=json_response,
        )

    def add_items(self):
        pass


    def set_id(self):
        """
        Generate a unique 6-character URL-safe ID for the fridge.
        
        Uses Python's secrets module for cryptographically secure random generation.
        
        Generated IDs:
        - 6 characters long
        - URL-safe: A-Z, a-z, 0-9 only
        
        Examples: 'kB8mQ2', 'X7nP9s', 'A3mK8L'
        """
        if self.name is not None:
            id = re.sub(r"[^a-zA-Z0-9\-_~]+", "", self.name.lower())
            self.id = id
        else:
            keys = string.ascii_letters + string.digits  # A-Za-z0-9 (62 characters)
            self.id = ''.join(secrets.choice(keys) for _ in range(self.HASH_ID_LENGTH))

    def set_last_edited(self):
        """
        Sets last_edited to the current epoch time. Timezone defaults to UTC
        """
        self.last_edited = str(int(time.time()))

    def add_item(self, conditional_expression=None) -> DB_Response:
        """
        Adds a fridge item to the database
        """
        retries = self.HASH_COLLISION_RETRIES
        self.set_last_edited()
        for _ in range(retries):
            self.set_id()
            conditional_expression = "attribute_not_exists(id)"
            db_response = super().add_item(conditional_expression=conditional_expression)
            if db_response.status_code == 201:
                db_response.set_json_data(json.dumps({"id": self.id}))
                return db_response
            elif db_response.status_code == 409:
                continue
            else:
                return db_response
            
        # Fallback: exhausted all retries due to hash collisions
        return DB_Response(
            success = False,
            status_code = 500,
            message = f"Unable to generate unique fridge ID after {retries} retries"
        )

    def get_fridge_locations(self):
        pass

    def update_fridge_report(self, fridgeId: str, fridge_report: dict = None) -> DB_Response:
        """
        Updates or clears the latestFridgeReport field on a fridge.
        """
        db_response = self.get_item(fridgeId=fridgeId)
        if not db_response.is_successful():
            # Fridge was not found
            return db_response
        fridge_dict = json.loads(db_response.json_data)
        if fridge_report is None:
            fridge_dict.pop("latestFridgeReport", None)
        else:
            fridge_dict["latestFridgeReport"] = fridge_report
        fridge_json_data = json.dumps(fridge_dict)
        expression_attribute_names = {"#LFR": "latestFridgeReport", "#JD": "json_data"}
        expression_attribute_values = {":fj": {"S": fridge_json_data}}
        if fridge_report is None:
            update_expression = "SET #JD = :fj REMOVE #LFR"
        else:
            expression_attribute_values[":fr"] = {"S": json.dumps(fridge_report)}
            update_expression = "SET #JD = :fj, #LFR = :fr"
        try:
            self.db_client.update_item(
                TableName=self.TABLE_NAME,
                Key={"id": {"S": fridgeId}},
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                UpdateExpression=update_expression,
            )
        except ClientError as e:
            logger.error(e)
            return DB_Response(
                success=False,
                status_code=500,
                message="Unexpected AWS service exception",
            )
        return DB_Response(
            success=True, status_code=201, message="fridge_report was succesfully added"
        )

    def get_fridge_stats(self):
        
        response = self.db_client.scan(TableName = self.TABLE_NAME)
        # edit: using fridgereport.valid conditions for stat map
        stats = {condition: 0 for condition in FridgeReport.VALID_CONDITIONS}
        stats["total"] = 0
        stats["no_report"] = 0
        stats["unknown"] = 0

     
        if "Items" in response:
            for item in response['Items']: 
                stats["total"]+=1
                # get data from value under key S as string from the 
                # db table
                json_data = item.get("json_data", {}).get("S", "{}")
                #convert json string to object 
                dict_data = json.loads(json_data)
                # get fridge report 
                latestFridgeReport = dict_data.get("latestFridgeReport", None)
                # edit: added no report for admin knowledge
                if not latestFridgeReport: 
                    stats["no_report"] += 1
                    continue
                
                if (latestFridgeReport and "condition" in latestFridgeReport): 
                    condition = latestFridgeReport["condition"].lower(); 
                    if (condition in stats): 
                        stats[condition]+=1
                    elif condition: # edit: if new condition, then we want to set to 1.
                        stats["unknown"] += 1  # include it in response but with warning 
                        logger.error(f"Unknown condition encountered: '{condition}'")
        return DB_Response(
            success=True, 
            status_code=200, 
            message="Fetched the most recent fridge stats", 
            #back in string format 
            json_data=json.dumps(stats)
        )   
        

# good, dirty, out of order, not at location
class FridgeReport(DB_Item):
    TABLE_NAME = f"fridge_report_{DB_Item.STAGE}"
    VALID_CONDITIONS = {"good", "dirty", "out of order", "not at location", "ghost"}
    VALID_FOOD_PERCENTAGE = {0, 1, 2, 3}
    FIELD_VALIDATION = {
        "notes": {"required": False, "max_length": 256, "type": "S"},
        "fridgeId": {
            "required": True,
            "min_length": Fridge.MIN_ID_LENGTH,
            "max_length": Fridge.MAX_ID_LENGTH,
            "type": "S",
        },
        "photoUrl": {
            "required": False,
            "max_length": 2048,
            "type": "S",
        },
        "epochTimestamp": {"required": False, "type": "N"},
        "timestamp": {"required": False, "type": "S"},
        "condition": {"required": True, "type": "S", "choices": VALID_CONDITIONS},
        "foodPercentage": {
            "required": True,
            "type": "N",
            "choices": VALID_FOOD_PERCENTAGE,
        },
        "userId": {"required": False, "type": "S"},
    }

    def __init__(
        self, db_client: "botocore.client.DynamoDB", fridge_report: dict = None
    ):
        super().__init__(db_client=db_client)
        if fridge_report is not None:
            fridge_report = self.process_fields(fridge_report)
            self.notes: str = fridge_report.get("notes", None)
            self.condition: str = fridge_report.get("condition", None)
            self.photoUrl: str = fridge_report.get("photoUrl", None)
            self.fridgeId: str = fridge_report.get("fridgeId", None)
            self.foodPercentage: int = fridge_report.get("foodPercentage", None)
            self.userId: str = fridge_report.get("userId", None)
            # timestamp and epochTimestamp have the same time but in different formats
            self.timestamp: str = fridge_report.get(
                "timestamp", None
            )  # ISO formatted timestamp for api clients
            self.epochTimestamp: str = fridge_report.get(
                "epochTimestamp", None
            )  # Epoch timestamp for querying

    def get_report_history(self, fridge_id, next_token=None):
        exclusive_start_key = None
        if next_token:
            try:
                decoded_token = base64.urlsafe_b64decode(
                    next_token.encode("utf-8") + b"=" * (-len(next_token) % 4)
                )
                exclusive_start_key = json.loads(decoded_token)
                if (
                    not isinstance(exclusive_start_key, dict)
                    or exclusive_start_key.get("fridgeId", {}).get("S") != fridge_id
                    or "N" not in exclusive_start_key.get("epochTimestamp", {})
                ):
                    raise ValueError("Cursor does not match fridgeId")
            except (ValueError, TypeError, UnicodeDecodeError, AttributeError):
                return DB_Response(
                    success=False,
                    status_code=400,
                    message="Invalid nextToken",
                )

        query_parameters = {
            "TableName": self.TABLE_NAME,
            "KeyConditionExpression": "fridgeId = :fridgeId",
            "ExpressionAttributeValues": {":fridgeId": {"S": fridge_id}},
            "ScanIndexForward": False,
            "Limit": 5,
        }
        if exclusive_start_key:
            query_parameters["ExclusiveStartKey"] = exclusive_start_key

        result = self.db_client.query(**query_parameters)
        reports = [
            json.loads(item["json_data"]["S"])
            for item in result.get("Items", [])
        ]
        last_evaluated_key = result.get("LastEvaluatedKey")
        response = {
            "reports": reports,
            "nextToken": (
                base64.urlsafe_b64encode(
                    json.dumps(last_evaluated_key).encode("utf-8")
                )
                .decode("utf-8")
                .rstrip("=")
                if last_evaluated_key
                else None
            ),
        }
        return DB_Response(
            success=True,
            status_code=200,
            message="Successfully found fridge report history",
            json_data=json.dumps(response),
        )

    def delete_report(self, fridge_id, epoch_timestamp):
        """Delete a report and refresh the fridge's cached latest report if needed.

        If the deleted report was the newest, use the next newest report or clear
        latestFridgeReport when no reports remain.
        """
        if not isinstance(fridge_id, str) or not fridge_id:
            return DB_Response(
                success=False, status_code=400, message="Missing required field: fridgeId"
            )
        if not isinstance(epoch_timestamp, str) or not re.fullmatch(
            r"[0-9]+", epoch_timestamp
        ):
            return DB_Response(
                success=False,
                status_code=400,
                message="Invalid epochTimestamp",
            )
        epoch_timestamp = epoch_timestamp.lstrip("0") or "0"
        if len(epoch_timestamp) > 38:
            return DB_Response(
                success=False,
                status_code=400,
                message="Invalid epochTimestamp",
            )

        try:
            fridge_response = Fridge(db_client=self.db_client).get_item(
                fridgeId=fridge_id
            )
        except ClientError as e:
            logger.error(e)
            return DB_Response(
                success=False,
                status_code=500,
                message="Unexpected AWS service exception",
            )
        if not fridge_response.is_successful():
            return fridge_response

        try:
            delete_response = self.db_client.delete_item(
                TableName=self.TABLE_NAME,
                Key={
                    "fridgeId": {"S": fridge_id},
                    "epochTimestamp": {"N": epoch_timestamp},
                },
                ReturnValues="ALL_OLD",
            )
        except ClientError as e:
            logger.error(e)
            return DB_Response(
                success=False,
                status_code=500,
                message="Unexpected AWS service exception",
            )
        if "Attributes" not in delete_response:
            return DB_Response(
                success=False,
                status_code=404,
                message="Fridge report was not found",
            )

        fridge_dict = json.loads(fridge_response.json_data)
        latest_report = fridge_dict.get("latestFridgeReport")
        if (
            isinstance(latest_report, dict)
            and str(latest_report.get("epochTimestamp")) == epoch_timestamp
        ):
            try:
                query_response = self.db_client.query(
                    TableName=self.TABLE_NAME,
                    KeyConditionExpression="fridgeId = :fridgeId",
                    ExpressionAttributeValues={":fridgeId": {"S": fridge_id}},
                    ScanIndexForward=False,
                    Limit=1,
                    ConsistentRead=True,
                )
            except ClientError as e:
                logger.error(e)
                return DB_Response(
                    success=False,
                    status_code=500,
                    message="Unexpected AWS service exception",
                )
            reports = query_response.get("Items", [])
            next_latest_report = (
                json.loads(reports[0]["json_data"]["S"]) if reports else None
            )
            fridge_update_response = Fridge(db_client=self.db_client).update_fridge_report(
                fridgeId=fridge_id, fridge_report=next_latest_report
            )
            if not fridge_update_response.is_successful():
                return fridge_update_response

        return DB_Response(
            success=True,
            status_code=200,
            message="Fridge report was successfully deleted",
        )

    def set_timestamp(self):
        """
        Sets epochTimestamp and timestamp fields
        timestamp is ISO formatted date/time and is what the API user will use
        epochTimestamp will be what is used to query the database
        """
        utc_time = datetime.datetime.now(datetime.timezone.utc)
        self.epochTimestamp = str(int(utc_time.timestamp()))
        self.timestamp = utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def object_to_dict(self):
        """
        Converts object into a dictionary
        """
        object_dict = {}
        for key in self.FIELD_VALIDATION:
            val = getattr(self, key)
            if val is not None:
                object_dict[key] = val
        return object_dict

    def add_item(self) -> DB_Response:
        self.set_timestamp()
        fridge_report_dict = self.object_to_dict()
        db_response = super().add_item()
        if not db_response.is_successful():
            return db_response
        #updates the latestFridgeReport field in the Fridge table
        Fridge(db_client=self.db_client).update_fridge_report(fridgeId=self.fridgeId, fridge_report=fridge_report_dict)
        db_response.set_json_data(json.dumps({'fridgeId': self.fridgeId, 'timestamp': self.timestamp}))
        return db_response


class FridgeHistory(DB_Item):
    def __init__(self, db_client: "botocore.client.DynamoDB"):
        super().__init__(db_client=db_client)


class Tag(DB_Item):
    REQUIRED_FIELDS = ["tag_name"]
    TABLE_NAME = f"tag_{DB_Item.STAGE}"
    # Tag Class constants
    MIN_TAG_LENGTH = 3
    MAX_TAG_LENGTH = 32

    def __init__(self, db_client: "botocore.client.DynamoDB", tag_name: str = None):
        super().__init__(db_client=db_client)
        self.tag_name = self.format_tag(tag_name)

    def format_tag(self, tag_name: str) -> str:
        # tag_name is alphanumeric, all lowercased, may include hyphen and underscore but no spaces.
        if tag_name:
            tag_name = tag_name.lower().replace(" ", "")
        return tag_name

    @staticmethod
    def is_valid_tag_name(tag_name: str) -> Tuple[bool, str]:
        # valid tag name is alphanumeric, all lowercased, may include hyphen and underscore but no spaces.
        if tag_name is None:
            message = "Missing required fields: tag_name"
            return False, message
        length_tag_name = len(tag_name)
        is_tag_length_valid = (
            length_tag_name >= Tag.MIN_TAG_LENGTH
            and length_tag_name <= Tag.MAX_TAG_LENGTH
        )
        if tag_name and is_tag_length_valid:
            for x in tag_name:
                if not x.isalnum() and x not in ["_", "-"]:
                    message = "tag_name contains invalid characters"
                    return False, message
            message = ""
            return True, message
        else:
            message = f"Length of tag_name is {length_tag_name}. It should be >= {Tag.MIN_TAG_LENGTH} but <= {Tag.MAX_TAG_LENGTH}."
            return False, message

    def add_item(self) -> DB_Response:
        has_required_fields, field = self.has_required_fields()
        if not has_required_fields:
            return DB_Response(
                message=f"Missing Required Field: {field}",
                status_code=400,
                success=False,
            )
        is_valid_field = self.is_valid_tag_name(self.tag_name)
        if not is_valid_field:
            return DB_Response(
                message=f"Tag Name Can Only Contain Letters, Numbers, Hyphens and Underscore: {self.tag_name}",
                status_code=400,
                success=False,
            )
        item = {"tag_name": {"S": self.tag_name}}

        try:
            self.db_client.put_item(TableName=self.TABLE_NAME, Item=item)
        except self.db_client.exceptions.ResourceNotFoundException as e:
            message = f"Cannot do operations on a non-existent table: {Tag.TABLE_NAME}"
            logging.error(message)
            return DB_Response(message=message, status_code=500, success=False)
        except ClientError as e:
            logging.error(e)
            return DB_Response(
                message="Unexpected AWS service exception",
                status_code=500,
                success=False,
            )
        return DB_Response(
            message="Tag was succesfully added", status_code=200, success=True
        )

 
    def write_stats_toS3(self, bucket = "cfm-cache", key = "stats/fridge_stats.json"): 
        stats_response = self.get_fridge_stats()
        # if there is an error
        if not stats_response.is_successful(): 
            return stats_response
        s3 = boto3.client("s3")
        # put object in s3
        s3.put_object(Bucket = bucket, Key = key, Body = stats_response.json_data, ContentType = "application/json")
        return DB_Response(success = True,message=f"Fridge stats written to s3://{bucket}/{key}", status_code= 200)
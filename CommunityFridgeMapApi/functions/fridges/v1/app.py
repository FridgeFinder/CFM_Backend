import os
import logging
import json

try:
    from db import get_ddb_connection, Fridge, DB_Response
except:
    # If it gets here it's because we are performing a unit test. It's a common error when using lambda layers
    # Here is an example of someone having a similar issue:
    # https://stackoverflow.com/questions/69592094/pytest-failing-in-aws-sam-project-due-to-modulenotfounderror
    from dependencies.python.db import get_ddb_connection, Fridge, DB_Response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class FridgeHandler:
    @staticmethod
    def lambda_handler(event: dict, ddbclient: "botocore.client.DynamoDB") -> dict:
        """
        Extracts the necessary data from events dict, and executes a function corresponding
        to the event httpMethod
        """
        httpMethod = event.get("httpMethod", None)
        body = event.get("body", None)
        pathParameters = event.get("pathParameters", None) or {}
        queryStringParameters = event.get("queryStringParameters", None) or {}
        tag = queryStringParameters.get("tag", None)
        fridgeId = pathParameters.get("fridgeId", None)
        db_response = None
        if httpMethod == "GET":
            if fridgeId:
                db_response = Fridge(db_client=ddbclient).get_item(fridgeId)
            else:
                db_response = Fridge(db_client=ddbclient).get_items(tag=tag)
        elif httpMethod == "POST":
            if body is not None:
                body = json.loads(body)
                db_response = Fridge(db_client=ddbclient, fridge=body).add_item()
        elif httpMethod == "PATCH":
            if not fridgeId:
                db_response = DB_Response(False, 400, "Invalid Fridge ID")
            elif body is None:
                db_response = DB_Response(
                    False, 400, "Request body is required"
                )
            else:
                try:
                    patch = json.loads(body)
                except json.JSONDecodeError:
                    db_response = DB_Response(
                        False, 400, "Request body must be valid JSON"
                    )
                else:
                    if not isinstance(patch, dict):
                        db_response = DB_Response(
                            False, 400, "Request body must be a JSON object"
                        )
                    else:
                        db_response = Fridge(db_client=ddbclient).patch_item(
                            fridgeId=fridgeId, patch=patch
                        )
        else:
            Fridge(db_client=ddbclient).warm_lambda()
            db_response = DB_Response(False, 400, "httpMethod missing")
        return db_response.api_format()


def lambda_handler(
    event: dict, context: "awslambdaric.lambda_context.LambdaContext"
) -> dict:
    env = os.environ["Environment"]
    ddbclient = get_ddb_connection(env)
    return FridgeHandler.lambda_handler(event, ddbclient)

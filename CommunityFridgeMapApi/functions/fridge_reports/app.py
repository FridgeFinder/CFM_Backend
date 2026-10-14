import os
import logging
import json

try:
    from db import get_ddb_connection, FridgeReport, Fridge, DB_Response
except:
    # If it gets here it's because we are performing a unit test. It's a common error when using lambda layers
    # Here is an example of someone having a similar issue:
    # https://stackoverflow.com/questions/69592094/pytest-failing-in-aws-sam-project-due-to-modulenotfounderror
    from dependencies.python.db import (
        get_ddb_connection,
        FridgeReport,
        Fridge,
        DB_Response,
    )

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class FridgReportHandler:
    def __init__():
        pass

    @staticmethod
    def lambda_handler(event: dict, ddbclient: "botocore.client.DynamoDB") -> dict:
        """
        Extracts the necessary data from events dict, and executes a function corresponding
        to the event httpMethod
        """
        body = event.get("body", None)
        fridge_id = event.get("pathParameters", {}).get("fridgeId", None)
        if body is not None:
            body = json.loads(body)
            body["fridgeId"] = fridge_id
        httpMethod = event.get("httpMethod", None)
        db_response = None
        if httpMethod == "POST":
            db_response = FridgeReport(
                db_client=ddbclient, fridge_report=body
            ).add_item()
        elif httpMethod == "GET":
            if event.get("resource", "").endswith("/reports/history"):
                query_parameters = event.get("queryStringParameters") or {}
                db_response = FridgeReport(db_client=ddbclient).get_report_history(
                    fridge_id=fridge_id,
                    next_token=query_parameters.get("nextToken"),
                )
            else:
                db_response = Fridge(db_client=ddbclient).get_latest_report(
                    fridgeId=fridge_id
                )
        else:
            FridgeReport(db_client=ddbclient).warm_lambda()
            db_response = DB_Response(False, 400, "httpMethod missing")
        return db_response.api_format()


def lambda_handler(
    event: dict, context: "awslambdaric.lambda_context.LambdaContext"
) -> dict:
    env = os.environ["Environment"]
    ddbclient = get_ddb_connection(env)
    return FridgReportHandler.lambda_handler(event, ddbclient)

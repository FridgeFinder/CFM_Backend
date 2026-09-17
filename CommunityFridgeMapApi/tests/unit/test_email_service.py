from http import client
from CommunityFridgeMapApi.functions.email_service.v1.app import ContactHandler
from dependencies.python.db import get_ddb_connection
import unittest
from dependencies.python.db import Fridge
import json


class SESClientMock:
    def __init__(self):
        self.send_count = 0

    def send_email(
        self,
        Source,
        Destination,
        Message,
        ReplyToAddresses=None,
        **kwargs,
    ):
        self.send_count += 1
        return {"MessageId": 1}


class ContactHandlerTest(unittest.TestCase):
    def test_format_email(self):
        formatted_email = ContactHandler.format_email("email", "body", "name")
        self.assertEqual(formatted_email, "From: name email\r\nMessage: body")

    def test_lambda_handler_no_body(self):
        response = ContactHandler.lambda_handler({}, client=SESClientMock())
        self.assertEqual(response["statusCode"], 400)
        body = json.loads(response["body"])
        self.assertEqual(
            body, {"message": "Unable to send Email. Missing Required Fields"}
        )

    def test_lambda_handler_missing_fields(self):
        event = {"body": {}}
        response = ContactHandler.lambda_handler(event, client=SESClientMock())
        body = json.loads(response["body"])
        self.assertEqual(
            body, {"message": "Unable to send Email. Missing Required Fields"}
        )

    def test_extract_body_fields(self):
        body = json.dumps(
            {
                "name": "name",
                "email": "email",
                "subject": "subject",
                "message": "message",
            }
        )
        (
            message,
            subject,
            sender,
            senderEmailAddress,
            website,
        ) = ContactHandler.extract_body_fields(body)
        self.assertEqual(message, "message")
        self.assertEqual(sender, "name")
        self.assertEqual(subject, "FridgeFinder Contact: subject. From: name")
        self.assertEqual(senderEmailAddress, "email")
        self.assertIsNone(website)

    def test_lambda_handler_blocks_honeypot_submission(self):
        body = json.dumps(
            {
                "name": "name",
                "email": "email",
                "subject": "subject",
                "message": "message",
                "website": "https://spam.example",
            }
        )
        client = SESClientMock()

        with self.assertLogs(level="WARNING") as logs:
            response = ContactHandler.lambda_handler(
                event={"body": body}, client=client
            )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(client.send_count, 0)
        self.assertTrue(
            any("website honeypot" in message for message in logs.output)
        )

    def test_lambda_handler(self):
        body = json.dumps(
            {
                "name": "name",
                "email": "email",
                "subject": "subject",
                "message": "message",
            }
        )
        event = {"body": body}
        client = SESClientMock()
        response = ContactHandler.lambda_handler(event=event, client=client)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(client.send_count, 1)
        message = json.loads(response["body"])["message"]
        self.assertEqual(message, "Successfully Sent Email!")

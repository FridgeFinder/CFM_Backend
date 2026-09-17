# CFM_Backend

<p align="center">
  <a href="https://www.fridgefinder.app/">
    <img src="https://raw.githubusercontent.com/CollectiveFocus/CFM_Frontend/dev/public/feedback/happyFridge.svg" height="128">
  </a>
    <h1 align="center">Community Fridge Map</h1>
</p>

<p align="center">
  <a aria-label="Collective Focus logo" href="https://collectivefocus.site/">
    <img src="https://img.shields.io/badge/sponsor-Collective%20Focus-yellow?style=flat-square&labelColor=F6F6F6">
  </a>
  <a aria-label="GitHub Repo stars" href="https://github.com/FridgeFinder/CFM_Backend/">
    <img alt="" src="https://img.shields.io/github/stars/FridgeFinder/CFM_Backend?style=flat-square&labelColor=F6F6F6">
  </a>
  <img aria-label="GitHub contributors" alt="GitHub contributors" src="https://img.shields.io/github/contributors/FridgeFinder/CFM_Backend?style=flat-square&labelColor=F6F6F6">
  <img aria-label="GitHub commit activity (dev)" alt="GitHub commit activity (dev)" src="https://img.shields.io/github/commit-activity/m/FridgeFinder/CFM_Backend/dev?style=flat-square&labelColor=F6F6F6">
  <a aria-label="Join the community on Discord" href="https://discord.com/channels/955884900655972463/955886184159125534">
    <img alt="" src="https://img.shields.io/badge/Join%20the%20community-yellow.svg?style=flat-square&logo=Discord&labelColor=F6F6F6">
  </a>
</p>

A community fridge is a decentralized resource where businesses and individuals can [donate perishable food](https://www.thrillist.com/lifestyle/new-york/nyc-community-fridges-how-to-support). There are dozens of fridges hosted by volunteers across the country.

Fridge Finder is project sponsored by [Collective Focus](https://collectivefocus.site/), a community organization in Brooklyn, New York. Our goal is to make it easy for people to find fridge locations and get involved with food donation programs in their community. We are building a responsive, mobile first, multi-lingual web application with administrative controls for fridge maintainers. To join the project read our [contributing guidelines](https://github.com/CollectiveFocus/CFM_Frontend/blob/dev/docs/CONTRIBUTING.md) and [code of conduct](https://github.com/FridgeFinder/CFM_Backend/blob/dev/CODE_OF_CONDUCT.md). The application will be deployed to https://www.fridgefinder.app/

---

## Pre-Requisites

1. AWS CLI - [Install the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - **You DO NOT have to create an AWS account to use AWS CLI for this project, skip these steps if you don't want to create an AWS account**
   - AWS CLI looks for credentials when using it, but doesn't validate. So will need to set some fake one. But the region name matters, use any valid region name.
     ```sh
     $ aws configure
     $ AWS Access Key ID: [ANYTHING YOU WANT]
     $ AWS Secret Access Key: [ANYTHING YOUR HEART DESIRES]
     $ Default region nam: us-east-1
     $ Default output format [None]: (YOU CAN SKIP)
     ```
2. SAM CLI - [Install the SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
   - **You DO NOT need to create an aws account to use SAM CLI for this project, skip these steps if you don't want to create an aws account**
3. Python 3 - [Install Python 3](https://www.python.org/downloads/)
4. Docker - [Install Docker](https://docs.docker.com/get-docker/)

---

## Deployment

```bash
cd CommunityFridgeMapApi
sam build --use-container
sam deploy --config-file samconfig.toml
```

---

## Setup Local Database Connection

**Guide that was used:** https://betterprogramming.pub/how-to-deploy-a-local-serverless-application-with-aws-sam-b7b314c3048c

Follow these steps to get Dynamodb running locally

1. **Start a local DynamoDB service**
   ```sh
   $ docker compose up
   # OR if you want to run it in the background:
   $ docker compose up -d
   ```
2. **Create tables**
   ```sh
   $ ./scripts/create_local_dynamodb_tables.py
   ```
3. `cd CommunityFridgeMapApi/`
4. `sam build --use-container`
5. **Load data into your local Dynamodb tables**
   1. Fridge Data: `sam local invoke LoadFridgeDataFunction --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`
6. **Get data from your local Dynamodb tables**
   1. `aws dynamodb scan --table-name fridge_dev --endpoint-url http://localhost:4566`

---

## Build and Test Locally

Confirm that the following requests work for you

1. `cd CommunityFridgeMapApi/`
2. `sam build --use-container`
3. `sam local invoke HelloWorldFunction --event events/event.json`
   - response: `{"statusCode": 200, "body": "{\"message\": \"hello world\"}"}`
4. `sam local start-api`
5. `curl http://localhost:3000/hello`
   - response: `{"message": "hello world"}`

---

## API

Choose your favorite API platform for using APIs.
Recommend: https://www.postman.com/

### Fridge

### One Time Use

1. POST Fridge: `sam local invoke FridgesFunction --event events/local-post-fridge-event.json --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`
2. GET Fridges: `sam local invoke FridgesFunction --event events/local-event-get-fridges.json --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`
3. GET Fridges Filter By Tag: `sam local invoke FridgesFunction --event events/local-event-get-fridges-with-tag.json --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`

### Local Server

1. Start Server: `sam local start-api --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`
2. GET Fridges: Go to http://localhost:3000/v1/fridges
3. GET Fridge: Go to http://localhost:3000/v1/fridges/{fridgeId}
4. Get Fridges Filter By Tag: http://localhost:3000/v1/fridges?tag={TAG}
   - Example: http://localhost:3000/v1/fridges?tag=tag1
5. POST Fridge Example:

```
curl --location --request POST 'http://localhost:3000/v1/fridges' --header 'Content-Type: application/json' --data-raw '{
    "name": "LES Community Fridge #2",
    "verified": false,
    "location": {
        "name": "testing",
        "street": "466 Grand Street",
        "city": "New York",
        "state": "NY",
        "zip": "10002",
        "geoLat": 40.715207,
        "geoLng": -73.983748
    },
    "maintainer": {
        "name": "name",
        "organization": "org",
        "phone": "1234567890",
        "email": "test@test.com",
        "instagram": "https://www.instagram.com/les_communityfridge",
        "website": "https://linktr.ee/lescommunityfridge"
    },
    "notes": "notes",
    "photoUrl": "url.com"
}'
```

### Fridge Report

#### One Time Use

1. POST FridgeReport: `sam local invoke FridgeReportFunction --event events/local-fridge-report-event.json --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`
   - [OPTIONAL] Generate custom event Example: `sam local generate-event apigateway aws-proxy --method POST --path document --body "{\"condition\": \"working\", \"foodPercentage\": 0}" > events/local-fridge-report-event-2.json`
     - Add `"fridgeId": "{FRIDGEID}"` to pathParameter in generated file
2. Query Data: `aws dynamodb scan --table-name fridge_report_dev --endpoint-url http://localhost:4566`

#### Local Server

1. Start Server: `sam local start-api --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`
2. Make a POST Request to: `http://127.0.0.1:3000/v1/fridges/{fridgeId}/reports`
   - Example: `curl --location --request POST 'http://127.0.0.1:3000/v1/fridges/thefriendlyfridge/reports' --header 'Content-Type: application/json' --data-raw '{"condition": "good", "foodPercentage": 1}'`

### Image

1. Start local SAM API `sam local start-api --parameter-overrides ParameterKey=Environment,ParameterValue=local ParameterKey=Stage,ParameterValue=dev --docker-network cfm-network`
1. Upload image (replace `<file-path>` with your actual image path like `"@/home/user/Downloads/sample.webp"`)
   ```
   curl --request POST \
     --url http://localhost:3000/v1/photo \
     --header 'Content-Type: image/webp' \
     --data-binary "@<file-path>"
   ```

---

## Tests

Tests are defined in the `tests` folder in this project. Create Virtual Environment, use PIP to install the test dependencies, and run tests.



```bash
CFM_BACKEND$ cd CommunityFridgeMapApi

# Create and activate virtual environment
CommunityFridgeMapApi$ python3 -m venv myenv
CommunityFridgeMapApi$ source myenv/bin/activate

# Install dependencies (note: virtual environment is now active)
(myenv) CommunityFridgeMapApi$ pip install -r tests/requirements.txt

# Run unit tests
(myenv) CommunityFridgeMapApi$ python -m pytest tests/unit -v

# To test with coverage
(myenv) coverage run -m pytest tests/unit -v
(myenv) coverage report
(myenv) coverage html

#MacOs:
(myenv) open -a "Google Chrome" htmlcov/index.html

#Windows:
(myenv) start "Google Chrome" htmlcov/index.html

# When finished, deactivate virtual environment
(myenv) CommunityFridgeMapApi$ deactivate
CommunityFridgeMapApi$
```

---

## Useful AWS SAM commands

1. `sam validate -t template.yaml`
2. `sam build --use-container`
   - Use this command before running the backend if you updated the code
3. `sam local generate-event apigateway aws-proxy --method GET --path document --body "" > local-event.json`
   - Use this command to generate a REST API event

## Useful Dynamodb Commands

1. `aws dynamodb scan --table-name fridge_{stage} --endpoint-url http://localhost:4566`
2. `aws dynamodb scan --table-name fridge_report_{stage} --endpoint-url http://localhost:4566`

## Useful formatting Command

```bash
CFM_BACKEND$ bash .git/hooks/pre-commit
```

## Resources

Project Documentation

- [Architecture Brainstorming](https://docs.google.com/document/d/1FYClUD16KUY42_p93rZFHN-iyp94RU0Rtw517vj2jXs/edit)
- [Architecture](https://docs.google.com/document/d/1yZVGAxVn4CEZyyce_Zuha3oYOOU8ey7ArBvLbm7l4bw/edit)
- [Database Tables] (https://docs.google.com/document/d/16hjNHxm_ebZv8u_VolT1bdlJEDccqb7V67-Y6ljjUdY/edit?usp=sharing)
- [Development Workflow](https://docs.google.com/document/d/1m9Xqo4QUVEBjMD7sMjxSHa3CxxjvrHppwc0nrdWCAAc/edit)
- [Database Table Design](https://docs.google.com/document/d/16hjNHxm_ebZv8u_VolT1bdlJEDccqb7V67-Y6ljjUdY/edit?usp=sharing)

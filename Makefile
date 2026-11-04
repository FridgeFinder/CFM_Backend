API_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))CommunityFridgeMapApi
ENVIRONMENT ?= local
STAGE ?= dev
DOCKER_NETWORK ?= cfm-network
API_URL ?= http://localhost:3000
DYNAMODB_URL ?= http://localhost:4566

LOCAL_OPTIONS = --parameter-overrides ParameterKey=Environment,ParameterValue=$(ENVIRONMENT) ParameterKey=Stage,ParameterValue=$(STAGE) --docker-network "$(DOCKER_NETWORK)"

.PHONY: help build start-api post-fridge get-fridges get-fridges-by-tag \
	get-fridge patch-fridge post-report get-reports get-report-history \
	post-contact load-fridges scan-fridges scan-reports

help:
	@printf '%s\n' \
		'Run from the repository root:' \
		'  make build                  Build the SAM application using containers' \
		'  make start-api              Start the local API server' \
		'  make post-fridge            Invoke POST Fridge using its event file' \
		'  make get-fridges            Invoke GET Fridges using its event file' \
		'  make get-fridges-by-tag     Invoke GET Fridges using its tag event file' \
		'  make patch-fridge          Invoke PATCH Fridge using its event file' \
		'  make post-report           Invoke POST FridgeReport using its event file' \
		'  make post-contact          Invoke POST Contact using its event file' \
		'  make get-fridge FRIDGE_ID=...          GET one fridge from the API server' \
		'  make get-reports FRIDGE_ID=...         GET fridge reports from the API server' \
		'  make get-report-history FRIDGE_ID=...  GET the first report-history page' \
		'  make load-fridges          Load sample fridge data into the local database' \
		'  make scan-fridges          Scan the fridge table' \
		'  make scan-reports          Scan the report table' \
		'' \
		'Overrides: ENVIRONMENT, STAGE, DOCKER_NETWORK, API_URL, DYNAMODB_URL.' \
		'Invocation targets also accept EVENT (relative to CommunityFridgeMapApi).'

build:
	cd "$(API_DIR)" && sam build --use-container

start-api:
	cd "$(API_DIR)" && sam local start-api $(LOCAL_OPTIONS)

post-fridge: EVENT = events/local-post-fridge-event.json
get-fridges: EVENT = events/local-event-get-fridges.json
get-fridges-by-tag: EVENT = events/local-event-get-fridges-with-tag.json
patch-fridge: EVENT = events/local-patch-fridge-event.json
post-report: EVENT = events/local-fridge-report-event.json
post-contact: EVENT = events/local-contact-email.json

post-fridge get-fridges get-fridges-by-tag patch-fridge: FUNCTION = FridgesFunction
post-report: FUNCTION = FridgeReportFunction
post-contact: FUNCTION = ContactFunction

post-fridge get-fridges get-fridges-by-tag patch-fridge post-report post-contact:
	cd "$(API_DIR)" && sam local invoke $(FUNCTION) --event "$(EVENT)" $(LOCAL_OPTIONS)

get-fridge: API_PATH = /v1/fridges/$(FRIDGE_ID)
get-reports: API_PATH = /v1/fridges/$(FRIDGE_ID)/reports
get-report-history: API_PATH = /v1/fridges/$(FRIDGE_ID)/reports/history

get-fridge get-reports get-report-history:
	@test -n "$(FRIDGE_ID)" || { echo 'FRIDGE_ID is required, e.g. make $@ FRIDGE_ID=thefriendlyfridge' >&2; exit 1; }
	curl --fail-with-body --silent --show-error "$(API_URL)$(API_PATH)"
	@printf '\n'

load-fridges:
	cd "$(API_DIR)" && sam local invoke LoadFridgeDataFunction $(LOCAL_OPTIONS)

scan-fridges: TABLE = fridge_$(STAGE)
scan-reports: TABLE = fridge_report_$(STAGE)

scan-fridges scan-reports:
	aws dynamodb scan --table-name "$(TABLE)" --endpoint-url "$(DYNAMODB_URL)" --no-cli-pager

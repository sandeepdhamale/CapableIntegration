import json
import os
import logging
import http.client
from json import JSONEncoder

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Patient:
    pass

class ObjectEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


def lambda_handler(event, context):
    logger.info(f'event: {event}')
    body_json = event.get("body-json", None)
    body_params = body_json.split("&")
    param_values = {}
    for param_value in body_params:
        param = param_value.split('=')[0]
        value = param_value.split('=')[1]
        param_values[param] = value
        
    appointment_id = param_values.get('id')
    action = param_values.get('action')
    logger.info(f'appointment_id: {appointment_id}')
    logger.info(f'action: {action}')
    if appointment_id is not None and action == 'scheduled':
        acuity_base64_authorization = os.environ['acuity_base64_authorization']
        capablehealth_cognito_oauth2_authorization = os.environ['capablehealth_cognito_oauth2_authorization']
        capablehealth_cognito_oauth2_token_hostname = os.environ['capablehealth_cognito_oauth2_token_hostname']
        acuityscheduling_hostname = os.environ['acuityscheduling_hostname']
        capablehealth_hostname = os.environ['capablehealth_hostname']
        
        # Get the patient information from acuityscheduling
        acuityscheduling_http_conn = http.client.HTTPSConnection(acuityscheduling_hostname, timeout=5)
        acuityscheduling_http_payload = ''
        acuityscheduling_http_headers = {
          f'Authorization': f'Basic {acuity_base64_authorization}'
        }
        acuityscheduling_http_conn.request("GET", f"/api/v1/appointments/{appointment_id}", acuityscheduling_http_payload, acuityscheduling_http_headers)
        acuityscheduling_http_res = acuityscheduling_http_conn.getresponse()
        if acuityscheduling_http_res.status == 200:
            data = acuityscheduling_http_res.read()
            
            acuity_data = json.loads(data.decode("utf-8"))
            logger.info(f'acuity_data: {acuity_data}')
            first_name = acuity_data['firstName']
            last_name = acuity_data['lastName']
            phone = acuity_data['phone']
            email = acuity_data['email']
            
            patient_data = Patient()
            patient_data.email = email
            patient_data.first_name = first_name
            patient_data.last_name = last_name
            
            phone_nulber = {"number": phone}
            phones_attributes = [phone_nulber]
            patient_data.phones_attributes = phones_attributes
            patient = Patient()
            patient.patient = patient_data
            
            #Get capablehealth access token
            capablehealth_cognito_oauth2_http_conn = http.client.HTTPSConnection(capablehealth_cognito_oauth2_token_hostname, timeout=5)
            payload = 'grant_type=client_credentials'
            headers = {
              'Authorization': f'Basic {capablehealth_cognito_oauth2_authorization}',
              'Content-Type': 'application/x-www-form-urlencoded'
            }
            capablehealth_cognito_oauth2_http_conn.request("POST", "/oauth2/token", payload, headers)
            capablehealth_cognito_oauth2_http_res = capablehealth_cognito_oauth2_http_conn.getresponse()
            if capablehealth_cognito_oauth2_http_res.status == 200:
                data = capablehealth_cognito_oauth2_http_res.read()
            
                access_token_data = json.loads(data.decode("utf-8"))
                capablehealth_access_token = access_token_data['access_token']
                
                capablehealth_http_conn = http.client.HTTPSConnection(capablehealth_hostname, timeout=5)
                payload = json.dumps(patient, cls=ObjectEncoder)
                headers = {
                  'Authorization': f'Bearer {capablehealth_access_token}',
                  'Content-Type': 'application/json'
                }
                capablehealth_http_conn.request("POST", "/patients", payload, headers)
                capablehealth_http_res = capablehealth_http_conn.getresponse()
                if capablehealth_http_res.status == 201:
                    logger.info(f'Patient created successfully. appointment_id: {appointment_id}')
                    return {
                    'statusCode': 200,
                    'body': json.dumps('Message Received and processed successfully!')
                    }
                else:
                    logger.error(f'Failed to create the patient.')
                    logger.error(f'Response status code: {capablehealth_http_res.status}')
                    logger.error(f'Response status reason: {capablehealth_http_res.reason}')
                    data = capablehealth_http_res.read()
                    msg = data.decode("utf-8")
                    logger.error(f'Response message: {msg}')
                    logger.error(f'Patient data: {payload}')
                    return {
                        'statusCode': capablehealth_http_res.status,
                        'body': json.dumps('Failed to create patient.')
                    }
            else:
                logger.error(f"capablehealth access token service failed. response: {capablehealth_cognito_oauth2_http_res.status}")
                return {
                    'statusCode': 500,
                    'body': json.dumps(f"Internal server error. capablehealth access token api response: {capablehealth_cognito_oauth2_http_res.status}")
                }
        else:
            logger.error(f"acuityscheduling service failed. response: {acuityscheduling_http_res.status}")
            return {
                'statusCode': 500,
                'body': json.dumps(f"Internal server error. acuityscheduling service response: {acuityscheduling_http_res.status}")
            }
    else:
        logger.error(f"id parameter is missing in the payload or action is other than scheduled")
        return {
                'statusCode': 400,
                'body': json.dumps("'id' parameter is missing in the payload.")
            }
import requests
import os
import re
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SendGrid API Key and Unsubscribe Group ID
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
UNSUBSCRIBE_GROUP_ID = 18613 

# Airtable
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

# Function to normalize email by decapitalizing, removing aliases, etc.
def normalize_email(email):
    logging.debug(f"Normalizing email: {email}")
    email = email.lower()
    email = re.sub(r'\+.*(?=@)', '', email)  # Remove anything after + and before @
    normalized_email = email.strip()  # Also strip any leading or trailing whitespace
    logging.debug(f"Normalized email: {normalized_email}")
    return normalized_email

# Function to split and normalize multiple emails
def split_and_normalize_emails(email_string):
    logging.debug(f"Splitting and normalizing emails: {email_string}")
    emails = email_string.split(',')
    normalized_emails = [normalize_email(email) for email in emails]
    logging.debug(f"Resulting normalized emails: {normalized_emails}")
    return normalized_emails

# Function to get all records with 'Newsletter Consent' set to 'Consent Revoked' and 'Last Modified Newsletter Consent' within the last 2 hours
def get_revoked_consent_emails():
    logging.info("Fetching records with 'Consent Revoked' from Airtable...")
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Calculate the timestamp for 2 hours ago
    two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).isoformat() + 'Z'
    logging.debug(f"Timestamp for 2 hours ago: {two_hours_ago}")

    # Update the filter formula to check for both conditions
    filter_formula = f"AND({{Newsletter Consent}} = 'Consent Revoked', IS_AFTER({{Last Modified Newsletter Consent}}, '{two_hours_ago}'))"
    params = {
        "filterByFormula": filter_formula
    }
    
    response = requests.get(AIRTABLE_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        records = response.json().get('records', [])
        logging.debug(f"Fetched records: {records}")
        emails = []
        for record in records:
            if 'Email' in record['fields']:
                logging.debug(f"Processing record: {record}")
                emails.extend(split_and_normalize_emails(record['fields']['Email']))
        logging.info(f"Emails with 'Consent Revoked' and modified within the last 2 hours: {emails}")
        return emails
    else:
        logging.error(f"Failed to fetch records from Airtable: {response.status_code} - {response.text}")
        raise Exception(f"Failed to fetch records from Airtable: {response.status_code} - {response.text}")

# Function to get unsubscribes from SendGrid
def get_sendgrid_unsubscribes():
    logging.info("Fetching unsubscribed emails from SendGrid...")
    url = f"https://api.sendgrid.com/v3/asm/groups/{UNSUBSCRIBE_GROUP_ID}/suppressions"
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        unsubscribes = [normalize_email(email) for email in response.json()]
        logging.info(f"Fetched unsubscribed emails: {unsubscribes}")
        return unsubscribes
    else:
        logging.error(f"Failed to get unsubscribes from SendGrid: {response.status_code} - {response.text}")
        raise Exception(f"Failed to get unsubscribes from SendGrid: {response.status_code} - {response.text}")

# Function to add emails to SendGrid unsubscribe group
def add_to_sendgrid_unsubscribes(emails):
    logging.info(f"Adding {len(emails)} emails to the SendGrid unsubscribe group...")
    url = f"https://api.sendgrid.com/v3/asm/groups/{UNSUBSCRIBE_GROUP_ID}/suppressions"
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "recipient_emails": emails
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 201:
        logging.info(f"Successfully added {len(emails)} emails to the SendGrid unsubscribe group.")
    else:
        logging.error(f"Failed to add emails to SendGrid unsubscribe group: {response.status_code} - {response.text}")
        raise Exception(f"Failed to add emails to SendGrid unsubscribe group: {response.status_code} - {response.text}")

# Main function
def main():
    try:
        # Step 1: Get emails with 'Consent Revoked' and modified within the last 2 hours from Airtable
        revoked_emails = get_revoked_consent_emails()
        logging.debug(f"Revoked emails: {revoked_emails}")
        
        # Step 2: Get unsubscribed emails from SendGrid
        unsubscribed_emails = get_sendgrid_unsubscribes()
        logging.debug(f"Unsubscribed emails: {unsubscribed_emails}")
        
        # Step 3: Identify emails that need to be added to the SendGrid unsubscribe group
        emails_to_add = [email for email in revoked_emails if email not in unsubscribed_emails]
        logging.debug(f"Emails to add: {emails_to_add}")
        
        if emails_to_add:
            logging.info(f"Adding {len(emails_to_add)} emails to the SendGrid unsubscribe group...")
            add_to_sendgrid_unsubscribes(emails_to_add)
        else:
            logging.info("No new emails to add to the SendGrid unsubscribe group.")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()

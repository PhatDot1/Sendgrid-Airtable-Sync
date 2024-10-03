import requests
import os
import re
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SendGrid API Key
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

# Airtable
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

# Function to normalize email
def normalize_email(email):
    logging.debug(f"Normalizing email: {email}")
    email = email.lower()
    email = re.sub(r'\+.*(?=@)', '', email)  # Remove anything after + and before @
    normalized_email = email.strip()  # Strip leading/trailing whitespace
    logging.debug(f"Normalized email: {normalized_email}")
    return normalized_email

# Function to split and normalize multiple emails
def split_and_normalize_emails(email_string):
    logging.debug(f"Splitting and normalizing emails: {email_string}")
    emails = email_string.split(',')
    normalized_emails = [normalize_email(email) for email in emails]
    logging.debug(f"Resulting normalized emails: {normalized_emails}")
    return normalized_emails

# Function to get all records with 'Last Modified Main Email' within the last day and 'Newsletter Consent' not equal to 'Consent Revoked'
def get_recent_emails():
    logging.info("Fetching records with 'Last Modified Main Email' in the last day and 'Newsletter Consent' not 'Consent Revoked'...")
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Calculate the timestamp for 1 day ago
    one_day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z'
    logging.debug(f"Timestamp for 1 day ago: {one_day_ago}")

    # Filter formula to check 'Last Modified Main Email' within the last day and 'Newsletter Consent' not 'Consent Revoked'
    filter_formula = f"AND(NOT({{Newsletter Consent}} = 'Consent Revoked'), IS_AFTER({{Last Modified Main Email}}, '{one_day_ago}'))"
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
        logging.info(f"Emails modified within the last day: {emails}")
        return emails
    else:
        logging.error(f"Failed to fetch records from Airtable: {response.status_code} - {response.text}")
        raise Exception(f"Failed to fetch records from Airtable: {response.status_code} - {response.text}")

# Function to upsert contacts in SendGrid
def upsert_sendgrid_contacts(emails):
    logging.info(f"Upserting {len(emails)} contacts to SendGrid 'All Contacts' list...")
    
    url = "https://api.sendgrid.com/v3/marketing/contacts"
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    contacts = [{"email": email} for email in emails]
    data = {
        "contacts": contacts
    }
    
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code == 202:
        logging.info(f"Successfully upserted {len(emails)} contacts to SendGrid.")
    else:
        logging.error(f"Failed to upsert contacts to SendGrid: {response.status_code} - {response.text}")
        raise Exception(f"Failed to upsert contacts to SendGrid: {response.status_code} - {response.text}")

# Main function
def main():
    try:
        # Step 1: Get emails modified within the last day and 'Newsletter Consent' not 'Consent Revoked' from Airtable
        recent_emails = get_recent_emails()
        logging.debug(f"Recent emails: {recent_emails}")
        
        # Step 2: Upsert emails to SendGrid "All Contacts" list
        if recent_emails:
            logging.info(f"Upserting {len(recent_emails)} emails to SendGrid 'All Contacts'.")
            upsert_sendgrid_contacts(recent_emails)
        else:
            logging.info("No emails to upsert to 'All Contacts'.")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()

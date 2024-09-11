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

# Function to get all records with 'Newsletter Consent' set to 'Consent Given' and 'Last Modified Newsletter Consent' within the last 2 hours
def get_given_consent_emails():
    logging.info("Fetching records with 'Consent Given' from Airtable...")
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Calculate the timestamp for 2 hours ago
    two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).isoformat() + 'Z'
    logging.debug(f"Timestamp for 2 hours ago: {two_hours_ago}")

    # Update the filter formula to check for both conditions
    filter_formula = f"AND({{Newsletter Consent}} = 'Consent Given', IS_AFTER({{Last Modified Newsletter Consent}}, '{two_hours_ago}'))"
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
        logging.info(f"Emails with 'Consent Given' and modified within the last 2 hours: {emails}")
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

# Function to remove emails from SendGrid unsubscribe group
def remove_from_sendgrid_unsubscribes(emails):
    logging.info(f"Removing {len(emails)} emails from the SendGrid unsubscribe group...")
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for email in emails:
        url = f"https://api.sendgrid.com/v3/asm/groups/{UNSUBSCRIBE_GROUP_ID}/suppressions/{email}"
        
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 204:
            logging.info(f"Successfully removed {email} from the SendGrid unsubscribe group.")
        else:
            logging.error(f"Failed to remove {email} from SendGrid unsubscribe group: {response.status_code} - {response.text}")
            raise Exception(f"Failed to remove {email} from SendGrid unsubscribe group: {response.status_code} - {response.text}")

# Function to add or update contacts in SendGrid
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
        # Step 1: Get emails with 'Consent Given' and modified within the last 2 hours from Airtable
        given_consent_emails = get_given_consent_emails()
        logging.debug(f"Consent Given emails: {given_consent_emails}")
        
        # Step 2: Get unsubscribed emails from SendGrid
        unsubscribed_emails = get_sendgrid_unsubscribes()
        logging.debug(f"Unsubscribed emails: {unsubscribed_emails}")
        
        # Step 3: Identify emails that need to be removed from the SendGrid unsubscribe group
        emails_to_remove = [email for email in given_consent_emails if email in unsubscribed_emails]
        logging.debug(f"Emails to remove: {emails_to_remove}")
        
        if emails_to_remove:
            logging.info(f"Removing {len(emails_to_remove)} emails from the SendGrid unsubscribe group...")
            remove_from_sendgrid_unsubscribes(emails_to_remove)
        else:
            logging.info("No emails to remove from the SendGrid unsubscribe group.")
        
        # Step 4: Upsert emails to SendGrid "All Contacts" list
        if given_consent_emails:
            logging.info(f"Upserting {len(given_consent_emails)} emails to SendGrid 'All Contacts'.")
            upsert_sendgrid_contacts(given_consent_emails)
        else:
            logging.info("No emails to upsert to 'All Contacts'.")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()

import requests
import re

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
    email = email.lower()
    email = re.sub(r'\+.*(?=@)', '', email)  # Remove anything after + and before @
    return email.strip()  # Also strip any leading or trailing whitespace

# Function to split and normalize multiple emails
def split_and_normalize_emails(email_string):
    emails = email_string.split(',')
    return [normalize_email(email) for email in emails]

# Function to get all records with 'Newsletter Consent' set to 'Consent Revoked' from Airtable
def get_revoked_consent_emails():
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    filter_formula = "({Newsletter Consent} = 'Consent Revoked')"
    params = {
        "filterByFormula": filter_formula
    }
    
    response = requests.get(AIRTABLE_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        records = response.json().get('records', [])
        emails = []
        for record in records:
            if 'Email' in record['fields']:
                emails.extend(split_and_normalize_emails(record['fields']['Email']))
        return emails
    else:
        raise Exception(f"Failed to fetch records from Airtable: {response.status_code} - {response.text}")

# Function to get unsubscribes from SendGrid
def get_sendgrid_unsubscribes():
    url = f"https://api.sendgrid.com/v3/asm/groups/{UNSUBSCRIBE_GROUP_ID}/suppressions"
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        unsubscribes = [normalize_email(email) for email in response.json()]
        return unsubscribes
    else:
        raise Exception(f"Failed to get unsubscribes from SendGrid: {response.status_code} - {response.text}")

# Function to add emails to SendGrid unsubscribe group
def add_to_sendgrid_unsubscribes(emails):
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
        print(f"Successfully added {len(emails)} emails to the SendGrid unsubscribe group.")
    else:
        raise Exception(f"Failed to add emails to SendGrid unsubscribe group: {response.status_code} - {response.text}")

# Main function
def main():
    # Step 1: Get emails with 'Consent Revoked' from Airtable
    revoked_emails = get_revoked_consent_emails()
    
    # Step 2: Get unsubscribed emails from SendGrid
    unsubscribed_emails = get_sendgrid_unsubscribes()
    
    # Step 3: Identify emails that need to be added to the SendGrid unsubscribe group
    emails_to_add = [email for email in revoked_emails if email not in unsubscribed_emails]
    
    if emails_to_add:
        print(f"Adding {len(emails_to_add)} emails to the SendGrid unsubscribe group...")
        add_to_sendgrid_unsubscribes(emails_to_add)
    else:
        print("No new emails to add to the SendGrid unsubscribe group.")

if __name__ == "__main__":
    main()

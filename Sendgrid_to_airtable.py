import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

# SendGrid and Unsubscribe Group ID
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
UNSUBSCRIBE_GROUP_ID = 18613

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
with open('credentials.json') as creds_file:
    creds_json = json.load(creds_file)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/18ORZTfeVGVCo7Wx4wzQMhMVPseCnGRT3W1wKEGNhSaw/edit#gid=0").sheet1

# Airtable
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

# Function to normalize email by decapitalizing, removing aliases, etc.
def normalize_email(email):
    email = email.lower()
    email = re.sub(r'\+.*(?=@)', '', email)  # Remove anything after + and before @
    return email

# Function to get unsubscribes from a specific suppression group in SendGrid
def get_unsubscribes():
    url = f"https://api.sendgrid.com/v3/asm/groups/{UNSUBSCRIBE_GROUP_ID}/suppressions"
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        unsubscribes = response.json()
        return unsubscribes
    else:
        raise Exception(f"Failed to get unsubscribes: {response.status_code} - {response.text}")

# Function to get emails from Google Sheets
def get_emails_from_sheet():
    return [normalize_email(email) for email in sheet.col_values(1)]  # Normalize emails from the sheet

# Function to search for a record in Airtable where the 'Email' field contains the given email
def search_airtable_record(email):
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    filter_formula = f"FIND('{email}', {{Email}})"
    params = {
        "filterByFormula": filter_formula
    }
    
    response = requests.get(AIRTABLE_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        records = response.json().get('records', [])
        return records if records else None
    else:
        raise Exception(f"Failed to search Airtable for {email}: {response.status_code} - {response.text}")

# Function to update Airtable record
def update_airtable_record(record_id, email):
    update_data = {
        "fields": {
            'Newsletter Consent': 'Consent Revoked',
            'Consent Snapshot': f'Newsletter - Consent Revoked - {datetime.now().strftime("%Y-%m-%d")} - N/A'
        }
    }
    
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    update_url = f"{AIRTABLE_URL}/{record_id}"
    response = requests.patch(update_url, json=update_data, headers=headers)
    
    if response.status_code == 200:
        return True
    else:
        print(f"Failed to update Airtable record for {email}: {response.status_code} - {response.text}")
        return False

# Function to add email to Google Sheets
def add_email_to_sheet(email):
    sheet.append_row([email])

# Main function
def main():
    unsubscribes = get_unsubscribes()
    sheet_emails = get_emails_from_sheet()
    
    # Normalize unsubscribes and find missing emails
    missing_emails = [normalize_email(email) for email in unsubscribes if normalize_email(email) not in sheet_emails]
    
    if missing_emails:
        print("Emails not in Google Sheet:")
        for email in missing_emails:
            print(email)
            # Search for the email in Airtable
            records = search_airtable_record(email)
            if records:
                record_id = records[0]['id']
                if update_airtable_record(record_id, email):
                    print(f"Updated Airtable record for {email}")
                    add_email_to_sheet(email)
                    print(f"Added {email} to Google Sheet")
            else:
                print(f"No matching record found in Airtable for {email}")
    else:
        print("All unsubscribed emails are already in the Google Sheet.")

if __name__ == "__main__":
    main()

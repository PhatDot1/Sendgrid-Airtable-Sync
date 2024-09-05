import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import json

# Set up Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# Read Google credentials from the credentials.json file (as you specified)
with open('credentials.json') as creds_file:
    creds_json = json.load(creds_file)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/18ORZTfeVGVCo7Wx4wzQMhMVPseCnGRT3W1wKEGNhSaw/edit#gid=0").worksheet("Exmailing")

# Set up Airtable API
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_IDS_AND_TABLES = [
    (os.getenv('AIRTABLE_BASE_ID_1'), os.getenv('AIRTABLE_TABLE_ID_1')),
    (os.getenv('AIRTABLE_BASE_ID_2'), os.getenv('AIRTABLE_TABLE_ID_2')),
    (os.getenv('AIRTABLE_BASE_ID_3'), os.getenv('AIRTABLE_TABLE_ID_3')),
    (os.getenv('AIRTABLE_BASE_ID_4'), os.getenv('AIRTABLE_TABLE_ID_4'))
]

# Function to search for a record by Record ID in multiple Airtable tables
def search_airtable_record(record_id):
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    for base_id, table_name in AIRTABLE_BASE_IDS_AND_TABLES:
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}?filterByFormula=RECORD_ID()='{record_id}'"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            records = response.json().get('records', [])
            if records:
                return records[0], base_id, table_name  # Return the first matching record and its base/table details

    return None, None, None  # If no record is found in any table


# Function to update the email by prefixing a # symbol
def update_airtable_email(record_id, base_id, table_name, email):
    if not email.startswith("#"):
        new_email = f"#{email}"
    
        update_data = {
            "fields": {
                'Email': new_email
            }
        }

        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }

        update_url = f"https://api.airtable.com/v0/{base_id}/{table_name}/{record_id}"
        response = requests.patch(update_url, json=update_data, headers=headers)

        if response.status_code == 200:
            return True
        else:
            print(f"Failed to update Airtable record {record_id}: {response.status_code} - {response.text}")
            return False
    else:
        print(f"Email {email} already has a # prefix, no update needed.")
        return True


# Function to search for records by Email in multiple Airtable tables and update all occurrences of the email
def search_and_update_email(email):
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Loop through all bases and tables to search for email
    for base_id, table_name in AIRTABLE_BASE_IDS_AND_TABLES:
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}?filterByFormula=Email='{email}'"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            records = response.json().get('records', [])
            for record in records:
                email_field = record['fields'].get('Email')

                # Check if the email matches the email we're searching for and if it needs to be updated
                if email_field and email_field == email and not email_field.startswith('#'):
                    record_id = record['id']

                    # Call the update function to add # to the email
                    if update_airtable_email(record_id, base_id, table_name, email_field):
                        print(f"Updated email {email_field} with # in base {base_id}, table {table_name}")
                    else:
                        print(f"Failed to update email {email_field} in base {base_id}, table {table_name}")
        else:
            print(f"Failed to search Airtable base {base_id}, table {table_name}: {response.status_code} - {response.text}")


# Function to add email to a different Airtable table
def add_email_to_airtable(email, web3_github, web3_external, ai_external, ai_github):
    # Airtable base and table where email needs to be added
    base_id = os.getenv('NEW_AIRTABLE_BASE_ID')
    table_name = os.getenv('NEW_AIRTABLE_TABLE_NAME')
    
    # Data to insert
    insert_data = {
        "fields": {
            "Email": email,
            "Status": "Checked",  # Single select field value
            "Main Base People Table": "N/A",  # Always N/A
            "Web3 GitHub Table": "True" if web3_github else "False",
            "Web3 External Hacker Table": "True" if web3_external else "False",
            "AI External Hacker Table": "True" if ai_external else "False",
            "AI GitHub Table": "True" if ai_github else "False"
        }
    }

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Insert the email into the specified Airtable base/table
    insert_url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    response = requests.post(insert_url, json=insert_data, headers=headers)

    if response.status_code == 200:
        print(f"Email {email} successfully added to table {table_name} with status 'Checked'.")
        return True
    else:
        print(f"Failed to add email {email} to table {table_name}: {response.status_code} - {response.text}")
        return False


# Main function to process the Google Sheet and update Airtable records
def main():
    # Get all records from the Google Sheet
    records = sheet.get_all_values()

    # Loop through each record in the Google Sheet
    for i, row in enumerate(records, start=1):  # 'i' is the row index in the sheet (starting from 1)
        if len(row) == 0:
            continue  # Skip completely empty rows

        record_id = row[0]  # Column A contains the Airtable Record ID
        status = row[1] if len(row) > 1 else ''  # Safely get status (Column B), defaulting to empty if not present

        if status.lower() == 'done':
            continue  # Skip already processed records

        # Search for the record in Airtable by ID
        record, base_id, table_name = search_airtable_record(record_id)

        # Initialize the single-select field values
        web3_github = False
        web3_external = False
        ai_external = False
        ai_github = False

        if record:
            email = record['fields'].get('Email')
            if email:
                # Set the single-select values based on which table the record was found in
                if base_id == os.getenv('AIRTABLE_BASE_ID_3') and table_name == os.getenv('AIRTABLE_TABLE_ID_3'):
                    ai_external = True  # Found in Web3 GitHub Table

                if base_id == os.getenv('AIRTABLE_BASE_ID_4') and table_name == os.getenv('AIRTABLE_TABLE_ID_4'):
                    web3_github = True  # Found in Web3 External Hacker Table

                if base_id == os.getenv('AIRTABLE_BASE_ID_2') and table_name == os.getenv('AIRTABLE_TABLE_ID_2'):
                    web3_external = True  # Found in AI External Hacker Table

                if base_id == os.getenv('AIRTABLE_BASE_ID_1') and table_name == os.getenv('AIRTABLE_TABLE_ID_1'):
                    ai_github = True  # Found in AI GitHub Table

                # Update the email by adding # at the start if needed
                if update_airtable_email(record_id, base_id, table_name, email):
                    # Mark as done in Google Sheet
                    sheet.update_cell(i, 2, 'Done')  # Update column B with 'Done'
                    print(f"Updated record {record_id} and marked as done.")

                    # Search for the same email in all other tables and update
                    search_and_update_email(email)

                    # Add the email to the specified base/table with single-select fields
                    if add_email_to_airtable(email, web3_github, web3_external, ai_external, ai_github):
                        print(f"Email {email} added to the new Airtable table with status 'Checked'.")
                    else:
                        print(f"Failed to add email {email} to the new Airtable table.")
                else:
                    print(f"Failed to update email for record {record_id}.")
            else:
                print(f"No email field found for record {record_id}.")
        else:
            print(f"Record ID {record_id} not found in Airtable.")

if __name__ == "__main__":
    main()

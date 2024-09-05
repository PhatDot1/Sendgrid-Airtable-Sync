import requests
import os

# Set up Airtable API
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_IDS_AND_TABLES = [
    (os.getenv('AIRTABLE_BASE_ID_1'), os.getenv('AIRTABLE_TABLE_ID_1')),
    (os.getenv('AIRTABLE_BASE_ID_2'), os.getenv('AIRTABLE_TABLE_ID_2')),
    (os.getenv('AIRTABLE_BASE_ID_3'), os.getenv('AIRTABLE_TABLE_ID_3')),
    (os.getenv('AIRTABLE_BASE_ID_4'), os.getenv('AIRTABLE_TABLE_ID_4')),
    (os.getenv('AIRTABLE_BASE_ID_5'), os.getenv('AIRTABLE_TABLE_ID_5'))  
]

# Function to standardize email (remove the part after '+' in the local part)
def standardize_email(email):
    if '+' in email:
        local_part, domain_part = email.split('@')
        if '+' in local_part:
            local_part = local_part.split('+')[0]
        return f"{local_part}@{domain_part}"
    return email

# Function to update email in Airtable
def update_airtable_email(record_id, base_id, table_name, email_field_name, new_email):
    update_data = {
        "fields": {
            email_field_name: new_email
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

# Function to search for records containing a + symbol in the email
def search_and_standardize_emails():
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Loop through all bases and tables to search for emails containing '+'
    for base_id, table_name in AIRTABLE_BASE_IDS_AND_TABLES:
        # Log the base and table currently being processed
        print(f"Processing base: {base_id}, table: {table_name}")

        # Check if we are in the 5th table
        if base_id == os.getenv('AIRTABLE_BASE_ID_5'):
            email_field_name = "Main Email"
        else:
            email_field_name = "Email"

        # Correctly quote the '+' and field name in the filter formula
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}?filterByFormula=FIND('+',{{{email_field_name}}})>0"
        
        # Log the request URL
        print(f"Request URL: {url}")
        
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            records = response.json().get('records', [])
            for record in records:
                email_field = record['fields'].get(email_field_name)

                # Standardize the email (remove + and any alias part)
                if email_field and '+' in email_field:
                    new_email = standardize_email(email_field)
                    if new_email != email_field:
                        record_id = record['id']

                        # Call the update function to standardize the email
                        if update_airtable_email(record_id, base_id, table_name, email_field_name, new_email):
                            print(f"Updated email {email_field} to {new_email} in base {base_id}, table {table_name}")
                        else:
                            print(f"Failed to update email {email_field} in base {base_id}, table {table_name}")
        else:
            # Log the failure, including the base and table where it occurred
            print(f"Failed to search Airtable base {base_id}, table {table_name}: {response.status_code} - {response.text}")


# Main function to run the email standardization
if __name__ == "__main__":
    search_and_standardize_emails()

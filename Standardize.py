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
    try:
        local_part, domain_part = email.split('@')
        if '+' in local_part:
            local_part = local_part.split('+')[0]  # Remove everything after '+'
        return f"{local_part}@{domain_part}"
    except Exception as e:
        print(f"Error standardizing email {email}: {e}")
        return email  # Return the original email if there is an error

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

    # Log the response from the update attempt
    print(f"Attempting to update email for record {record_id} to {new_email}")
    print(f"API response status: {response.status_code}")
    print(f"API response text: {response.text}")

    if response.status_code == 200:
        print(f"Successfully updated email {new_email} for record {record_id}")
        return True
    else:
        print(f"Failed to update Airtable record {record_id}: {response.status_code} - {response.text}")
        return False

# Function to search for records containing a + symbol in the email and standardize them
def search_and_standardize_emails():
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    total_found = 0
    total_updated = 0

    # Loop through all bases and tables to search for emails containing '+'
    for base_id, table_name in AIRTABLE_BASE_IDS_AND_TABLES:
        print(f"Processing base: {base_id}, table: {table_name}")

        # Determine the email field name (Main Email for the 5th table)
        if base_id == os.getenv('AIRTABLE_BASE_ID_5'):
            email_field_name = "Main Email"
        else:
            email_field_name = "Email"

        # Filter records where the email contains '+'
        url = f"https://api.airtable.com/v0/{base_id}/{table_name}?filterByFormula=FIND('+',{{{email_field_name}}})>0"
        print(f"Request URL: {url}")
        
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            records = response.json().get('records', [])
            found_count = len(records)
            total_found += found_count
            print(f"Found {found_count} records in base {base_id}, table {table_name} with {email_field_name} containing '+'")

            # Process each record one by one
            for record in records:
                email_field = record['fields'].get(email_field_name)

                # Log each email found
                if email_field and '+' in email_field:
                    print(f"Processing record ID: {record['id']}, Email: {email_field}")

                    # Standardize the email (remove + and any alias part)
                    new_email = standardize_email(email_field)

                    # Log the new email before updating
                    print(f"Standardized email: {new_email} (from {email_field})")

                    if new_email != email_field:  # Only update if there's a change
                        print(f"Updating record {record['id']} to new email: {new_email}")
                        if update_airtable_email(record['id'], base_id, table_name, email_field_name, new_email):
                            total_updated += 1
                        else:
                            print(f"Failed to update record {record['id']}.")
                    else:
                        print(f"No changes required for email {email_field}")

        else:
            print(f"Failed to search Airtable base {base_id}, table {table_name}: {response.status_code} - {response.text}")

    # Final confirmation message
    print(f"Script completed. Total records found with '+': {total_found}")
    print(f"Total records updated: {total_updated}")


# Main function to run the email standardization
if __name__ == "__main__":
    search_and_standardize_emails()

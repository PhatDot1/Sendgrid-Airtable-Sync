import os
import gspread
import requests
import logging
import json
import re
from oauth2client.service_account import ServiceAccountCredentials
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
with open('credentials.json') as creds_file:
    creds_json = json.load(creds_file)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

# Define the retry session function
def requests_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Define the email extraction function
def extract_email(text):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    if matches:
        return matches[0].strip('\"<>[]()')
    return None

# Define the GitHub API handler class
class GitHubApiHandler:
    def __init__(self, api_keys):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.request_count = 0
        self.max_requests_per_key = 3650

    def get_headers(self):
        return {'Authorization': f'token {self.api_keys[self.current_key_index]}'}

    def check_and_switch_key(self):
        remaining_requests = self.get_remaining_requests()
        logger.info(f"Remaining requests for current key: {remaining_requests}")
        if remaining_requests < 10:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            self.request_count = 0
            logger.info(f"Switched to new API key: {self.current_key_index + 1}")

    def get_remaining_requests(self):
        headers = self.get_headers()
        url = 'https://api.github.com/rate_limit'
        response = requests_retry_session().get(url, headers=headers)
        if response.status_code == 200:
            rate_limit_data = response.json()
            remaining = rate_limit_data['rate']['remaining']
            return remaining
        return 0

    def get_user_info_from_github_api(self, profile_url):
        self.check_and_switch_key()
        headers = self.get_headers()
        username = profile_url.split('/')[-1]
        url = f'https://api.github.com/users/{username}'
        response = requests_retry_session().get(url, headers=headers)
        if response.status_code != 200:
            logger.info(f"Failed to fetch user info for {profile_url}, status code: {response.status_code}")
            return None
        user_data = response.json()
        email = user_data.get('email', '') or self.get_email_from_readme(username, headers)
        return email

    def get_email_from_readme(self, username, headers):
        url = f'https://raw.githubusercontent.com/{username}/{username}/main/README.md'
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return extract_email(response.text)
        return None

# Define Google Sheets interaction functions
def get_sheet_data(sheet, sheet_name, range):
    worksheet = sheet.worksheet(sheet_name)
    return worksheet.get(range)

def update_sheet_data(sheet, sheet_name, range, values):
    worksheet = sheet.worksheet(sheet_name)
    worksheet.update(range, values)

# Process batches of records from Google Sheets
def process_batch(sheet, github_api_handler):
    records = sheet.get_all_records()
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        for record in batch:
            profile_url = record['Profile URL']
            if record['Done?'] != 'Yes' and profile_url:
                logger.info(f"Processing record: {record['Username']} with GitHub URL: {profile_url}")
                try:
                    email = github_api_handler.get_user_info_from_github_api(profile_url)
                    if email:
                        # Update the 'Done?' field in Sheet1
                        update_sheet_data(sheet, 'Sheet1', f'D{i+2}', [['Yes']])
                        # Add data to Sheet2
                        update_sheet_data(sheet, 'Sheet2', f'A{i+2}:E{i+2}', [[record['Username'], record['User ID'], profile_url, email, record['Repo']]])
                except Exception as e:
                    logger.error(f"An error occurred while processing {profile_url}: {e}")

# Main function
def main():
    try:
        # Load GitHub API keys
        github_api_keys = os.environ['MY_GITHUB_API_KEYS'].split(',')

        # Initialize GitHub API handler
        github_api_handler = GitHubApiHandler(github_api_keys)

        # Open the Google Sheet
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1rKdG00VihG3zHRQLgQ6NteUHhdQxAqP2reLU8LCFotk/edit#gid=0")
        
        # Process records in batches of 100
        logger.info("Processing records in batches...")
        process_batch(sheet, github_api_handler)

    except Exception as e:
        logger.error(f"An error occurred in the main function: {e}")

if __name__ == "__main__":
    main()
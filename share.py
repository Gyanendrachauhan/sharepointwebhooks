from dotenv import load_dotenv
import os,requests
import logging
from flask import jsonify
from llm import upload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()
# Replace these variables with your actual values
client_id = os.getenv('client_id')
client_secret = os.getenv('client_secret')
tenant_id = os.getenv('tenant_id')
resource = os.getenv('resource')
site_id = os.getenv('site_id')

base_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items'

def get_access_token():
    url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    body = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': resource + '/.default'
    }

    try:
        response = requests.post(url, headers=headers, data=body)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.HTTPError as err:
        logger.error(f"Error obtaining access token: {err}")
        return None




def download_pdf_files(folder_id, folder_name, access_token, base_url):
    all_files = []
    url = f'{base_url}/{folder_id}/children'
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.HTTPError as err:
        logger.error(f"Failed to list items in folder {folder_name}. Error: {err}")
        return [], []

    for item in response.json().get('value', []):
        all_files.append(os.path.join(folder_name, item['name']))

        if 'folder' in item:
            _, child_files = download_pdf_files(item['id'], os.path.join(folder_name, item['name']), access_token, base_url)
            all_files.extend(child_files)
        elif 'file' in item and item['name'].endswith('.pdf'):
            local_file_path = os.path.join('local_directory', folder_name, item['name'])

            if not os.path.exists(local_file_path):
                file_url = f'{base_url}/{item["id"]}/content'
                try:
                    file_response = requests.get(file_url, headers=headers, stream=True)
                    file_response.raise_for_status()
                except requests.HTTPError as err:
                    logger.error(f"Failed to download file {item['name']}. Error: {err}")
                    continue

                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                with open(local_file_path, 'wb') as local_file:
                    for chunk in file_response.iter_content(chunk_size=1024):
                        if chunk:
                            local_file.write(chunk)

    return "Download successful!", all_files


def clean_local_directory(all_files):
    root_directory_path = r'C:\Users\Gyani\PycharmProjects\sharepointfinal\local_directory'
    for foldername, _, filenames in os.walk(root_directory_path):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(foldername, filename), root_directory_path)
            if rel_path not in all_files:
                os.remove(os.path.join(foldername, filename))



def upload_pdfs_to_server(filename_req):
    logger.info(f"Expected filenames: {filename_req}")
    access_token = get_access_token()
    base_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items'

    if not access_token:
        logger.error("Failed to retrieve access token.")
        return jsonify({"error": "Failed to retrieve access token"}), 401

    result, all_files = download_pdf_files('root', '', access_token, base_url)
    logger.info(f"All files downloaded: {all_files}")

    root_directory_path = r'C:\Users\Gyani\PycharmProjects\sharepointfinal\local_directory'
    files_list = []

    for foldername, _, filenames in os.walk(root_directory_path):
        for filename in filenames:
            if filename.endswith('.pdf') and filename in filename_req:
                file_path = os.path.join(foldername, filename)
                files_list.append(file_path)

    logger.info(f"Files to upload: {files_list}")
    upload_response = upload(files_list)

    if upload_response != 200:
        logger.error(f"Upload failed with response: {upload_response}")
        return jsonify({"error": "Failed to upload PDFs", "response": upload_response.text}), upload_response.status_code

    logger.info("Upload successful!")
    return 200

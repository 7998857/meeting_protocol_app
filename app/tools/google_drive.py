import os
import shutil

import pypandoc

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account


TEMP_DIR = "./tmp"
os.makedirs(TEMP_DIR, exist_ok=True)

# This is the id of the Meetingprotokolle folder in my Google Drive (Peter)
# Can be found by opening the folder in the browser and copying the id from
# the url:
#   https://drive.google.com/drive/u/0/folders/1vjy3XZEnc5LJl6xYx0dVIeqRlb4UdbfH
# CAVEAT: I tried locating the folder by name in the code, but it did not
# work, since the code operates the API under the service account. I.e.,
# it operates in the service account's drive, not the user's drive, and
# can therefore not see the user's folders.
# Therefore: You have to manually share the user's folder with the service
# account email address and then specify for the script.
FOLDER_ID = "1vjy3XZEnc5LJl6xYx0dVIeqRlb4UdbfH"


def export_to_google_drive(
    filename: str,
    meeting_protocol: str,
    folder_id: str = FOLDER_ID
):
    """
    Exports a meeting protocol to Google Drive as a Google Doc.
    Converts Markdown formatting to Google Docs formatting.

    Args:
        filename (str): The name for the Google Doc file
        meeting_protocol (str): The content of the meeting protocol in Markdown format
        folder_id (str): The id of the folder to upload to (default: FOLDER_ID)
            The default is the Meetingprotokolle folder id in my Google Drive (Peter).

    Returns:
        str: URL of the created Google Doc

    Requires:
        - Google API credentials configured
        - Required packages: google-auth, google-auth-oauthlib, google-api-python-client
    """
    service = authenticate_with_service_account('google_drive_credentials.json')

    tmp_docx_file = os.path.join(TEMP_DIR, f"{filename}.docx")
    
    convert_markdown_to_docx(meeting_protocol, tmp_docx_file, font='Arial')
    
    doc_id = upload_to_google_drive(
        service,
        filename,
        tmp_docx_file,
        folder_id
    )
    
    set_document_permissions(service, doc_id)

    # Get the document URL
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    # Clean up temporary files
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

    return doc_id, doc_url


def authenticate_with_service_account(service_account_file):
    # Define the required scopes
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    # Authenticate using service account
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=SCOPES)
    
    # Build the Drive service
    service = build('drive', 'v3', credentials=credentials)
    return service


def convert_markdown_to_docx(
    markdown_content: str,
    output_docx: str,
    font: str = 'Arial'
):
    """
    Converts a Markdown string to a DOCX file using Pandoc.
    
    :param markdown_content: Markdown content as a string.
    :param output_docx: Path to the output DOCX file.
    :param font: Font to use in the document (default: Arial)
    """
    
    # Create a temporary file for the markdown content
    tmp_md_file = os.path.join(TEMP_DIR, 'temp.md')
    with open(tmp_md_file, 'w') as f:
        f.write(markdown_content)

    reference_docx = "app/tools/reference.docx"

    pypandoc.convert_file(
        tmp_md_file,
        'docx',
        outputfile=output_docx,
        format='commonmark',
        extra_args=['--reference-doc', reference_docx]
    )


def upload_to_google_drive(
    drive_service,
    filename: str,
    docx_file_path: str,
    folder_id: str = None
):
    """
    Uploads a file to Google Drive.
    
    Args:
        drive_service: Google Drive service object
        filename: Name for the file
        docx_file_path: Path to the file to upload
        folder_id: ID of the folder to upload to (optional)
        
    Returns:
        ID of the uploaded file
    """
    file_metadata = {'name': filename}
    
    # If folder_id is provided, add it to the parent folders
    if folder_id:
        file_metadata['parents'] = [folder_id]
        
    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    # Media upload
    media = MediaFileUpload(docx_file_path, mimetype=mime_type)

    # Upload file
    doc_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    print(f"Uploaded file with ID: {doc_file.get('id')}")  

    doc_id = doc_file.get('id')

    return doc_id


def set_document_permissions(drive_service, doc_id):
    """
    Sets the permissions for a document to be readable by anyone with the link.
    
    Args:
        drive_service: Google Drive service object
        doc_id: ID of the document
    """
    # Make the document readable by anyone with the link
    drive_service.permissions().create(
        fileId=doc_id,
        body={
            'type': 'anyone',
            'role': 'writer'
        }
    ).execute()

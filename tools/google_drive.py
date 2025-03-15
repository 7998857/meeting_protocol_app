import os
import pickle
import pypandoc

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def export_to_google_drive(
    filename: str,
    meeting_protocol: str
):
    """
    Exports a meeting protocol to Google Drive as a Google Doc.
    Converts Markdown formatting to Google Docs formatting.

    Args:
        filename (str): The name for the Google Doc file
        meeting_protocol (str): The content of the meeting protocol in Markdown format

    Returns:
        str: URL of the created Google Doc

    Requires:
        - Google API credentials configured
        - Required packages: google-auth, google-auth-oauthlib, google-api-python-client
    """
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'google_docs_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Build the Drive API client
    drive_service = build('drive', 'v3', credentials=creds)

    # Build the Docs API client
    docs_service = build('docs', 'v1', credentials=creds)

    # Create an empty Google Doc
    doc_metadata = {
        'name': filename,
        'mimeType': 'application/vnd.google-apps.document'
    }

    doc_file = drive_service.files().create(
        body=doc_metadata,
        fields='id'
    ).execute()

    doc_id = doc_file.get('id')
    
    # Insert the plain text content first
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            'requests': [
                {
                    'insertText': {
                        'location': {
                            'index': 1
                        },
                        'text': meeting_protocol
                    }
                }
            ]
        }
    ).execute()

    # Make the document readable by anyone with the link
    drive_service.permissions().create(
        fileId=doc_id,
        body={
            'type': 'anyone',
            'role': 'reader'
        }
    ).execute()

    # Get the document URL
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    return doc_url


def convert_md_to_docx(input_md, output_docx):
    """
    Converts a Markdown file to a DOCX file using Pandoc.
    
    :param input_md: Path to the input Markdown file.
    :param output_docx: Path to the output DOCX file.
    """
    pypandoc.convert_file(input_md, 'docx', outputfile=output_docx)
    print(f"Converted {input_md} to {output_docx}")

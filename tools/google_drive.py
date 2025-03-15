import os
import pickle
import shutil
import tempfile

from docx import Document
import pypandoc

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


temp_dir = tempfile.mkdtemp()


def export_to_google_drive(
    filename: str,
    meeting_protocol: str,
    folder_name: str = "Meetingprotokolle"
):
    """
    Exports a meeting protocol to Google Drive as a Google Doc.
    Converts Markdown formatting to Google Docs formatting.

    Args:
        filename (str): The name for the Google Doc file
        meeting_protocol (str): The content of the meeting protocol in Markdown format
        folder_name (str): The name of the folder to upload to (default: "Meetingprotokolle")

    Returns:
        str: URL of the created Google Doc

    Requires:
        - Google API credentials configured
        - Required packages: google-auth, google-auth-oauthlib, google-api-python-client
    """
    creds = create_google_credentials()

    drive_service = build('drive', 'v3', credentials=creds)
    
    # Find or create the target folder
    folder_id = find_or_create_folder(drive_service, folder_name)
    
    tmp_docx_file = os.path.join(temp_dir, f"{filename}.docx")
    
    convert_markdown_to_docx(meeting_protocol, tmp_docx_file, font='Arial')
    
    doc_id = upload_to_google_drive(
        drive_service,
        filename,
        tmp_docx_file,
        folder_id
    )
    
    set_document_permissions(drive_service, doc_id)

    # Get the document URL
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    # Clean up temporary files
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    return doc_url


def create_google_credentials():
    """
    Creates Google API credentials for the application.
    
    Returns:
        Credentials object
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']  # Full access to Drive

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

    return creds


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
    # Create a reference docx with the specified font
    reference_docx = create_reference_docx(font)
    
    # Create a temporary file for the markdown content
    tmp_md_file = os.path.join(temp_dir, 'temp.md')
    with open(tmp_md_file, 'w') as f:
        f.write(markdown_content)

    pypandoc.convert_file(
        tmp_md_file,
        'docx',
        outputfile=output_docx,
        format='commonmark',
        extra_args=['--reference-doc', reference_docx]
    )


def create_reference_docx(font='Arial'):
    """
    Creates a reference DOCX file with the specified font.
    
    :param font: Font to use in the document
    :return: Path to the reference DOCX file
    """
    # Create a temporary directory for our work
    
    reference_docx = os.path.join(temp_dir, 'reference.docx')
    
    reference_md = os.path.join(temp_dir, 'reference.md')
    with open(reference_md, 'w') as f:
        f.write('# Heading 1\n\nNormal text\n\n**Bold text**\n\n*Italic text*\n\n')
        
    # First, create a basic docx
    pypandoc.convert_file(
        reference_md,
        'docx',
        outputfile=reference_docx,
        format='markdown'
    )
    
    doc = Document(reference_docx)
            
    # Change the font for all styles
    for style in doc.styles:
        if hasattr(style, 'font') and style.font:
            style.font.name = font
    
    # Save the modified document
    doc.save(reference_docx)
            
    return reference_docx


def find_or_create_folder(drive_service, folder_name):
    """
    Finds a folder by name or creates it if it doesn't exist.
    
    Args:
        drive_service: Google Drive service object
        folder_name: Name of the folder to find or create
        
    Returns:
        ID of the folder
    """
    # Search for the folder - use 'me' as the owner to find folders in your drive
    response = drive_service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and 'me' in owners and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    
    folders = response.get('files', [])
    
    # If folder exists, return its ID
    if folders:
        print(f"Found existing folder '{folder_name}' with ID: {folders[0]['id']}")
        return folders[0]['id']
    
    # If folder doesn't exist, create it
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    folder = drive_service.files().create(
        body=folder_metadata,
        fields='id'
    ).execute()
    
    print(f"Created new folder '{folder_name}' with ID: {folder.get('id')}")
    return folder.get('id')


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

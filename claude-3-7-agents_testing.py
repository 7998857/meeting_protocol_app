import json
import os
import sqlite3
import pickle
import time

import anthropic
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from tqdm import tqdm


load_dotenv()


def main():
    database = sqlite3.connect("database.db")
    cursor = database.cursor()
    transcript = get_transcript(cursor)
    participants = get_participants(cursor)
    topic, date = get_topic(cursor)

    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    speaker_mapping = get_speaker_mapping(
        client,
        transcript,
        participants,
        topic
    )
    print("Inferred speaker mapping")
    for speaker, participant in speaker_mapping["speaker_mapping"].items():
        transcript = transcript.replace(speaker, participant)

    for _ in tqdm(range(70), desc="Waiting to not hit rate limit..."):
        time.sleep(1)

    agenda = infer_agenda(client, transcript, topic)
    print("Inferred agenda")

    for _ in tqdm(range(70), desc="Waiting to not hit rate limit..."):
        time.sleep(1)

    meeting_protocol = create_meeting_protocol(client, transcript, agenda)
    print("Created meeting protocol")

    filename = create_filename(client, meeting_protocol, date)
    print("Created filename")

    meeting_protocol = format_for_google_docs(client, meeting_protocol)

    doc_url = export_to_google_drive(filename, meeting_protocol)
    print(f"Meeting protocol exported to Google Drive: {doc_url}")


def get_transcript(
    cursor: sqlite3.Cursor
) -> str:
    sql = "SELECT text FROM transcriptions WHERE meeting_id = 29"
    cursor.execute(sql)
    transcript = cursor.fetchone()[0]
    return transcript


def get_participants(
    cursor: sqlite3.Cursor
) -> list[str]:
    sql = """
        SELECT participants.name FROM meeting_participants
        INNER JOIN participants USING(participant_id)
        WHERE meeting_id=29
    """
    cursor.execute(sql)
    participants = cursor.fetchall()
    participants = [participant[0] for participant in participants]
    return participants


def get_topic(
    cursor: sqlite3.Cursor
) -> str:
    sql = "SELECT topic, date FROM meetings WHERE meeting_id = 29"
    cursor.execute(sql)
    topic, date = cursor.fetchone()
    return topic, date


def get_speaker_mapping(
    client: anthropic.Anthropic,
    transcript: str,
    participants: list[str],
    topic: str
) -> dict:
    example_json = {
        "speaker_mapping": {
            "Speaker A": "Participant 1",
            "Speaker B": "Participant 2",
        }
    }

    prompt = f"""
        We currently had a meeting and used a speech to text service to transcribe the meeting
        (the transcription is attached below).
        The meeting was held in German and the transcription model probably made some mistakes.
        For example, it has problems with correctly transcribing numbers and company names etc.
        Also, we saw, that sometimes adds the word 'zweitausendeins' or something similar to the transcript.
        So please be not confused by this.
        The transcription tool adde speaker labels to the transcript (like Speaker A, Speaker B and so on)
        but did not infer the participants names.
        Please infer which speaker is which participant. The list of participants is:
        {participants}
        Please respond with a JSON object with the following format:
        {example_json}

        Thanks for your help!

        The transcript is:
        {transcript}

        Please respond with the JSON object only.
    """

    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=1000,
        temperature=1,
        system=(
            "You are an AI assistant specialized in analyzing meeting transcripts. "
            "You can identify speakers, extract key information, and format the results as structured JSON. "
            "Always respond with only the requested JSON format without additional explanations."
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    )

    return json.loads(message.content[0].text)


def infer_agenda(
    client: anthropic.Anthropic,
    transcript: str,
    topic: str
) -> str:
    system_prompt = (
        "You are an AI assistant specialized in analyzing meeting transcripts. "
        "You can extract key information, summarize the content and infer an agenda "
        "based on the content of the transcript. "
        "Always respond with an agenda in bullet points. Make it concise and to the point. "
        "The agenda should be in the same language as the transcript. "
        "Please respond with the agenda only."
    )

    agenda_examples = [
        (
            "1. Einführung & Zielsetzung (5 Min)\n"
            "- Motivation für das Prozesschart (Moritz)\n"
            "Methodik: Kurze Präsentation\n"

            "2. Struktur & Erklärungen (25 Min)\n"
            "- Überblick über Prozess und Kernelemente\n"
            "- Sammlung offener Fragen\n"
            "Methodik: Strukturierte Durchsprache mit Notizen\n"

            "3. Offene Fragen & Priorisierung (10 Min)\n"
            "- Durchgehen und Priorisieren der Fragen\n"
            "Methodik: Eisenhower-Matrix (Sofort entscheiden/Diskutieren/Delegieren)\n"

            "4. Nächste Schritte (5 Min)\n"
            "- Maßnahmen und Verantwortlichkeiten festlegen\n"
            "Methodik: Klare Aufgabenzuweisung und ggf. Folgetermine"
        ),
        (
            "1. Einführung & Zielsetzung (10 Min)\n"
            "- Ziel des Meetings: Meinungsaustausch zum Prozess, Klärung von Unklarheiten\n"
            "- Agenda-Check: Passt die Agenda zum Ziel?\n"
            "Methodik: Agenda-Vorstellung mit Raum für Anpassungen\n"

            "2. Meinungsaustausch & offene Fragen (15 Min)\n"
            "- Kurzer Rückblick auf letztes Meeting\n"
            "- Identifikation von Sach- und Meinungsfragen\n"
            "Methodik: Offene Diskussionsrunde mit Kategorisierung der Fragen\n"

            "3. Thematische Einordnung (20 Min)\n"
            "- Priorisierung: Was klären wir heute, was später?\n"
            "Methodik: Kategorisierung in \"Heute klären\", \"Folgegespräch\", \"Anderer Kontext\"\n"

            "4. Nächste Schritte & Abschluss (5 Min)\n"
            "- Konkrete Maßnahmen und Verantwortlichkeiten\n"
            "- Festlegung weiterer Termine (falls nötig)\n"
        )
    ]

    agenda_prompt = (
        "The transcript you find below is the transcript of a meeting. It was automatically "
        "transcribed by a speech to text service. The transcription model probably made some "
        "mistakes. For example, it has problems with correctly transcribing numbers and company "
        "names etc. Also, we saw, that sometimes adds the word 'zweitausendeins' or something "
        "similar to the transcript. "
        "Also, it sometimes happens that the speaker labels of some parts of the transcript "
        "are not aligned well with who actually spoke. So please be not confused by this. "
        "Please infer an agenda from the transcript, i.e., an agenda which the meeting could "
        "have followed. "
        "Please respond with the agenda only and keep it concise and to the point. "
        "The transcript is: "
        f"{transcript} "
        f"\n\nThe topic of the meeting was: {topic} "
        "\n\nHere are some examples for a good agenda: "
        f"{agenda_examples} "
    )

    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=1000,
        temperature=1,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": agenda_prompt
                    }
                ]
            }
        ]
    )

    return message.content[0].text


def create_meeting_protocol(
    client: anthropic.Anthropic,
    transcript: str,
    agenda: str,
    date: str
) -> str:
    system_prompt = (
        "You are an AI assistant specialized in creating meeting protocols. "
        "You can create a meeting protocol from a transcript and an agenda. "
        "Always respond with a meeting protocol in bullet points. "
        "Make it detailed but still to the point. Keep it strictly to what was said in the meeting. "
        "And try to correctly infer the opinions of the participants and what was important to them. "
        "The meeting protocol should be in the same language as the transcript. "
    )

    meeting_protocol_prompt = (
        "The transcript you find below is the transcript of a meeting. It was automatically "
        "transcribed by a speech to text service. The transcription model probably made some "
        "mistakes. For example, it has problems with correctly transcribing numbers and company "
        "names etc. Also, we saw, that sometimes adds the word 'zweitausendeins' or something "
        "similar to the transcript. "
        "Also we found some parts of the transcript where the speaker labels are not aligned "
        "well with who actually spoke. So please be not confused by this. "
        "Please create a meeting protocol from the transcript and the agenda. In doing so, "
        "make sure to include all important points that were discussed and the decisions that were made. "
        "Further, try to infer the opinions of the participants and what was important to them "
        "such that I can send it to everyone afterwards and they are satisfied with the outcome. "
        "The agenda of the meeting is: "
        f"{agenda} "
        "The transcript is: "
        f"{transcript} "
        f"The date of the meeting was: {date} "
    )

    protocol_example_1 = open("few_shot_examples/protocol_2.txt", "r").read()
    protocol_example_2 = open("few_shot_examples/protocol_3.txt", "r").read()

    meeting_protocol_prompt += (
        f"\n\nHere are some examples for a good meeting protocol: "
        f"{protocol_example_1} "
        f"{protocol_example_2} "
    )

    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=5000,
        temperature=1,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": meeting_protocol_prompt
                    }
                ]
            }
        ]
    )

    return message.content[0].text


def create_filename(
    client: anthropic.Anthropic,
    meeting_protocol: str,
    date: str
) -> str:
    system_prompt = (
        "You are an AI assistant specialized in analyzing meeting protocols. "
        "You can create a descriptive filename for a meeting protocol and a date. "
        "Always respond with a filename only. The file is supposed to be uploaded to google drive. "
        "The date is: "
        f"{date} "
        "The meeting protocol is: "
        f"{meeting_protocol} "
        "Good examples for filenames are: "
        "25.02.25 - Retrospektive und Feedback, Abrunden von Meetingstrukturen und Entscheidungsformen\n"
        "20.01.2025 - Wertebesprechung orange und grün"
    )
    filename_prompt = (
        "Please create a filename for the meeting protocol. "
        "The date is: "
        f"{date} "
        "The meeting protocol is: "
        f"{meeting_protocol} "
    )

    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=100,
        temperature=1,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": filename_prompt
                    }
                ]
            }
        ]
    )
    return message.content[0].text


def format_for_google_docs(
    client: anthropic.Anthropic,
    meeting_protocol: str
) -> str:
    system_prompt = (
        "You are an AI assistant specialized in formatting meeting protocols for google docs. "
        "You can format a meeting protocol for google docs. "
        "Always respond with a formatted meeting protocol. Do not change anything in the protocol. "
        "Just make it look nice in google docs. "
    )
    format_prompt = (
        "The meeting protocol is: "
        f"{meeting_protocol} "
        "Please format it for google docs and respond with the formatted meeting protocol only. "
    )
    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=5000,
        temperature=1,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": format_prompt}]
            }
        ]
    )
    return message.content[0].text


def export_to_google_drive(
    filename: str,
    meeting_protocol: str
):
    """
    Exports a meeting protocol to Google Drive as a Google Doc.

    Args:
        filename (str): The name for the Google Doc file
        meeting_protocol (str): The content of the meeting protocol

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

    # Insert content into the document
    requests = [
        {
            'insertText': {
                'location': {
                    'index': 1
                },
                'text': meeting_protocol
            }
        }
    ]

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
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

    print(f"Meeting protocol exported to Google Drive: {doc_url}")
    return doc_url


if __name__ == "__main__":
    main()

"""
ToDo:
- replace the speaker labels with the participants names
go into more agentic style:

- let the model check the summary from each participants perspective
  (including Andrea, the Coach)
  and ask it to improve or add parts that are important to them and
  may be missing
- let the model check the agenda from each participants perspective
  and correct it if needed
- check from an outsiders perspective wether the summary
  is clear and understandable
- etc.
"""
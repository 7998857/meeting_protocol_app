import os
import sqlite3

import anthropic
from dotenv import load_dotenv


load_dotenv()

database = sqlite3.connect("database.db")
cursor = database.cursor()

sql = "SELECT text FROM transcriptions WHERE meeting_id = 29"
cursor.execute(sql)
transcript = cursor.fetchone()

sql = """
    SELECT participants.name FROM meeting_participants
    INNER JOIN participants USING(participant_id)
    WHERE meeting_id=29
"""
cursor.execute(sql)
participants = cursor.fetchall()
participants = [participant[0] for participant in participants]

client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

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
import pdb; pdb.set_trace()
print(message.content)

"""
ToDo:
- replace the speaker labels with the participants names
go into more agentic style:

- infer an agenda from the transcript
- create a meeting summary with examples (few shot prompt)
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
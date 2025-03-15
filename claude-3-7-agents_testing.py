import json
import os
import pickle
import sqlite3

import anthropic
from dotenv import load_dotenv

from tools.google_drive import export_to_google_drive
from tools.prompts_etc import PROMPTS, AGENDA_EXAMPLES


load_dotenv()
skip_cache = False


def main():
    database = sqlite3.connect("database.db")
    cursor = database.cursor()
    transcript = get_transcript(cursor)
    participants = get_participants(cursor)
    topic, date = get_topic(cursor)

    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    speaker_mapping = get_speaker_mapping(client, transcript, participants)
    print("Inferred speaker mapping")
    for speaker, participant in speaker_mapping["speaker_mapping"].items():
        transcript = transcript.replace(speaker, participant)

    agenda = infer_agenda(client, transcript, topic)
    print("Inferred agenda")

    meeting_protocol = create_meeting_protocol(
        client,
        transcript,
        agenda,
        date
    )
    print("Created meeting protocol")

    filename = create_filename(client, meeting_protocol, date)
    print("Created filename")

    meeting_protocol = ensure_markdown(client, meeting_protocol)
    print("Ensured markdown")
    
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
    participants: list[str]
) -> dict:
    example_json = {
        "speaker_mapping": {
            "Speaker A": "Participant 1",
            "Speaker B": "Participant 2",
        }
    }

    prompt = PROMPTS["speaker_mapping"]["message"].format(
        participants=participants,
        transcript=transcript,
        example_json=json.dumps(example_json)
    )

    message = call_claude_agent(
        client,
        prompt,
        PROMPTS["speaker_mapping"]["system"],
        1000,
        cache_key="speaker_mapping"
    )

    return json.loads(message)


def load_from_cache_if_exists(
    key: str
) -> dict | None:
    if skip_cache:
        return None
    if os.path.exists(f"cache/{key}.pkl"):
        return pickle.load(open(f"cache/{key}.pkl", "rb"))
    return None


def call_claude_agent(
    client: anthropic.Anthropic,
    message_prompt: str,
    system_prompt: str,
    max_tokens: int,
    cache_key: str = None
) -> str:
    # Try to load from cache if a cache key is provided
    if cache_key and not skip_cache:
        cached_result = load_from_cache_if_exists(cache_key)
        if cached_result:
            return cached_result
    
    # Call Claude API
    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=max_tokens,
        temperature=1,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": message_prompt
                    }
                ]
            }
        ]
    )
    result = message.content[0].text
    
    # Save to cache if a cache key is provided
    if cache_key and not skip_cache:
        save_to_cache(cache_key, result)
    
    return result


def save_to_cache(
    key: str,
    data: dict
) -> None:
    if skip_cache:
        return
    with open(f"cache/{key}.pkl", "wb") as f:
        pickle.dump(data, f)


def infer_agenda(
    client: anthropic.Anthropic,
    transcript: str,
    topic: str
) -> str:
    prompt = PROMPTS["infer_agenda"]["message"].format(
        transcript=transcript,
        topic=topic,
        agenda_examples=AGENDA_EXAMPLES
    )

    return call_claude_agent(
        client,
        prompt,
        PROMPTS["infer_agenda"]["system"],
        1000,
        cache_key="agenda"
    )


def create_meeting_protocol(
    client: anthropic.Anthropic,
    transcript: str,
    agenda: str,
    date: str
) -> str:
    protocol_example_1 = open("few_shot_examples/protocol_2.txt", "r").read()
    protocol_example_2 = open("few_shot_examples/protocol_3.txt", "r").read()

    protocol_examples = f"{protocol_example_1} {protocol_example_2}"

    prompt = PROMPTS["create_meeting_protocol"]["message"].format(
        transcript=transcript,
        agenda=agenda,
        date=date,
        protocol_examples=protocol_examples
    )

    return call_claude_agent(
        client,
        prompt,
        PROMPTS["create_meeting_protocol"]["system"],
        5000,
        cache_key="meeting_protocol"
    )


def create_filename(
    client: anthropic.Anthropic,
    meeting_protocol: str,
    date: str
) -> str:
    prompt = PROMPTS["create_filename"]["message"].format(
        meeting_protocol=meeting_protocol,
        date=date
    )

    return call_claude_agent(
        client,
        prompt,
        PROMPTS["create_filename"]["system"],
        100,
        cache_key="filename"
    )


def ensure_markdown(
    client: anthropic.Anthropic,
    meeting_protocol: str
) -> str:
    prompt = PROMPTS["ensure_markdown"]["message"].format(
        meeting_protocol=meeting_protocol
    )

    # No caching for formatting as it's the final step
    return call_claude_agent(
        client,
        prompt,
        PROMPTS["ensure_markdown"]["system"],
        5000,
        cache_key="ensure_markdown"
    )


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
- check from an outsiders perspective whether the summary
  is clear and understandable
- etc.
"""
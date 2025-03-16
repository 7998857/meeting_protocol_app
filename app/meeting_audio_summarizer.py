import json
import logging
import os
from pathlib import Path
import pickle
from typing import Union

import anthropic
import assemblyai as aai
from pydub import AudioSegment

from flask import current_app as app
import app.models as models
from app.database import db
from config import Config
from .tools.prompts_etc import PROMPTS, AGENDA_EXAMPLES
from .tools.google_drive import export_to_google_drive


logger = logging.getLogger(__name__)
logger.setLevel(Config.LOG_LEVEL)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

aai.settings.api_key = Config.ASSEMBLYAI_API_KEY


class MeetingAudioSummarizer:
    def __init__(
        self,
        anthropic_api_key: str = Config.ANTHROPIC_API_KEY,
        assemblyai_api_key: str = Config.ASSEMBLYAI_API_KEY,
        skip_cache: bool = False,
    ):
        self._skip_cache = skip_cache
        
        self._anthropic_client = anthropic.Anthropic(
            api_key=anthropic_api_key
        )

        self._transcriber = aai.Transcriber()

    def summarize_meeting(
        self,
        meeting: models.Meetings
    ) -> str:
        import pdb; pdb.set_trace()
        transcript = self._transcribe_audio(
            meeting.audio_file_path,
            len(meeting.participants),
            meeting.meeting_id
        )
        logger.info("Transcribed audio")
        db.session.add(transcript)
        db.session.commit()
        logger.info("Added transcript to database")

        speaker_mapping = self._get_speaker_mapping(
            self._anthropic_client,
            transcript.text,
            meeting.participants,
            meeting.meeting_id
        )
        logger.info("Inferred speaker mapping")
        transcript.speaker_mapping = json.dumps(speaker_mapping)
        db.session.commit()
        logger.info("Added speaker mapping to database")

        for speaker, participant in speaker_mapping["speaker_mapping"].items():
            transcript.text = transcript.text.replace(speaker, participant)
        logger.info("Applied speaker mapping to transcript")
        db.session.commit()
        logger.info("Updated transcript in database")

        agenda = self._infer_agenda(
            transcript.text,
            meeting.topic,
            meeting.meeting_id
        )
        logger.info("Inferred agenda")
        
        db.session.add(agenda)
        db.session.commit()
        logger.info("Added agenda to database")

        meeting_protocol = self._create_meeting_protocol(
            transcript.text,
            agenda.text,
            meeting.date,
            meeting.meeting_id
        )
        logger.info("Created meeting protocol")
        db.session.add(meeting_protocol)
        db.session.commit()
        logger.info("Added meeting protocol to database")

        filename = self._create_filename(
            meeting_protocol.text,
            meeting.date,
            meeting.meeting_id
        )
        logger.info("Created filename")

        meeting_protocol.language = self._ensure_language(
            meeting_protocol.text,
            meeting.meeting_id
        )
        logger.info("Ensured language")
        db.session.commit()
        logger.info("Updated meeting protocol in database")

        meeting_protocol.text = self._ensure_markdown(
            meeting_protocol.text,
            meeting.meeting_id
        )
        logger.info("Ensured markdown")
        db.session.commit()
        logger.info("Updated meeting protocol in database")
        
        drive_file_id, doc_url = export_to_google_drive(
            filename,
            meeting_protocol.text
        )
        logger.info(f"Meeting protocol exported to Google Drive: {doc_url}")

        meeting_protocol.google_drive_file_id = drive_file_id
        meeting_protocol.google_drive_filename = filename
        meeting_protocol.google_drive_url = doc_url
        db.session.commit()
        logger.info("Updated meeting protocol in database")

        return doc_url

    def _transcribe_audio(
        self,
        input_file_path: Union[str, Path],
        num_speakers: int,
        meeting_id: int
    ) -> aai.Transcript:
        cached_transcript = self._load_from_cache_if_exists(
            f"transcript_{meeting_id}"
        )
        if cached_transcript:
            return cached_transcript

        is_wav = Path(input_file_path).suffix == ".wav"

        if is_wav:
            audio = AudioSegment.from_wav(input_file_path)
            audio.export("/tmp/output.mp3", format="mp3")
            input_file_path = "/tmp/output.mp3"

        text = self._transcriber.transcribe(
            data=str(input_file_path),
            config=aai.TranscriptionConfig(
                language_code="de",
                speaker_labels=True,
                speakers_expected=num_speakers,
                speech_model="best",
            ),
        )

        transcript = models.Transcripts(
            meeting_id=meeting_id,
            text=text
        )

        if is_wav:
            os.remove("/tmp/output.mp3")

        return transcript
    
    def _get_speaker_mapping(
        self,
        client: anthropic.Anthropic,
        transcript: str,
        participants: list[str],
        meeting_id: int
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

        message = self._call_claude_agent(
            client,
            prompt,
            PROMPTS["speaker_mapping"]["system"],
            1000,
            cache_key=f"speaker_mapping_{meeting_id}"
        )

        return json.loads(message)

    def _call_claude_agent(
        self,
        message_prompt: str,
        system_prompt: str,
        max_tokens: int,
        cache_key: str = None
    ) -> str:
        # Try to load from cache if a cache key is provided
        if cache_key and not self._skip_cache:
            cached_result = self._load_from_cache_if_exists(cache_key)
            if cached_result:
                return cached_result
        
        # Call Claude API
        message = self._anthropic_client.messages.create(
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
        if cache_key and not self._skip_cache:
            self._save_to_cache(cache_key, result)
        
        return result

    def _load_from_cache_if_exists(
        self,
        key: str
    ) -> dict | None:
        if self._skip_cache:
            return None
        if os.path.exists(f"cache/{key}.pkl"):
            return pickle.load(open(f"cache/{key}.pkl", "rb"))
        return None

    def _save_to_cache(
        self,
        key: str,
        data: dict
    ) -> None:
        if self._skip_cache:
            return
        with open(f"cache/{key}.pkl", "wb") as f:
            pickle.dump(data, f)

    def _infer_agenda(
        self,
        transcript: str,
        topic: str,
        meeting_id: int
    ) -> str:
        prompt = PROMPTS["infer_agenda"]["message"].format(
            transcript=transcript,
            topic=topic,
            agenda_examples=AGENDA_EXAMPLES
        )

        text = self._call_claude_agent(
            prompt,
            PROMPTS["infer_agenda"]["system"],
            1000,
            cache_key=f"agenda_{meeting_id}"
        )
        agenda = models.Agendas(
            meeting_id=meeting_id,
            text=text
        )
        return agenda

    def _create_meeting_protocol(
        self,
        transcript: str,
        agenda: str,
        date: str,
        meeting_id: int
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

        text = self._call_claude_agent(
            prompt,
            PROMPTS["create_meeting_protocol"]["system"],
            5000,
            cache_key=f"meeting_protocol_{meeting_id}"
        )
        meeting_protocol = models.MeetingProtocols(
            meeting_id=meeting_id,
            text=text
        )
        return meeting_protocol

    def _create_filename(
        self,
        meeting_protocol: str,
        date: str,
        meeting_id: int
    ) -> str:
        prompt = PROMPTS["create_filename"]["message"].format(
            meeting_protocol=meeting_protocol,
            date=date
        )

        return self._call_claude_agent(
            prompt,
            PROMPTS["create_filename"]["system"],
            100,
            cache_key=f"filename_{meeting_id}"
        )

    def _ensure_language(
        self,
        transcript: str,
        meeting_protocol: str,
        meeting_id: int
    ) -> str:
        language = self._infer_language(transcript, meeting_id)

        prompt = PROMPTS["ensure_language"]["message"].format(
            meeting_protocol=meeting_protocol,
            language=language
        )

        return self._call_claude_agent(
            prompt,
            PROMPTS["ensure_language"]["system"],
            5000,
            cache_key=f"ensure_language_{meeting_id}"
        )
    
    def _infer_language(
        self,
        transcript: str,
        meeting_id: int
    ) -> str:
        prompt = PROMPTS["infer_language"]["message"].format(
            transcript=transcript[-500:]
        )

        return self._call_claude_agent(
            prompt,
            PROMPTS["infer_language"]["system"],
            5,
            cache_key=f"infer_language_{meeting_id}"
        )

    def _ensure_markdown(
        self,
        meeting_protocol: str,
        meeting_id: int
    ) -> str:
        prompt = PROMPTS["ensure_markdown"]["message"].format(
            meeting_protocol=meeting_protocol
        )

        return self._call_claude_agent(
            prompt,
            PROMPTS["ensure_markdown"]["system"],
            5000,
            cache_key=f"ensure_markdown_{meeting_id}"
        )
    

if __name__ == "__main__":
    summarizer = MeetingAudioSummarizer()
    summarizer.summarize_meeting(29)

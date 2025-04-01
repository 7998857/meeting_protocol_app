import json
import logging
import os
from pathlib import Path
import pickle
import time
from typing import Union

import anthropic
import assemblyai as aai
from pydub import AudioSegment

from .models import Meetings, Transcripts, Agendas, MeetingProtocols, Participants
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

DEBUG_RUN = True if os.environ.get("DEBUG_RUN", False) else False

aai.settings.api_key = Config.ASSEMBLYAI_API_KEY
ANTROPIC_COOL_DOWN_SECONDS = int(Config.ANTROPIC_COOL_DOWN_SECONDS)


class MeetingAudioSummarizer:
    def __init__(
        self,
        db,
        anthropic_api_key: str = Config.ANTHROPIC_API_KEY,
        debug_run: bool = DEBUG_RUN,
    ):
        self._db = db
        self._debug_run = debug_run
        
        self._anthropic_client = anthropic.Anthropic(
            api_key=anthropic_api_key
        )

        self._transcriber = aai.Transcriber()

    def summarize_meeting(
        self,
        meeting: type[Meetings]
    ) -> str:
        participants = meeting.participants.all()
        transcript = self._transcribe_audio(
            meeting.audio_file_path,
            len(participants),
            meeting.meeting_id
        )
        logger.info("Transcribed audio")
        if not self._debug_run:
            self._db.session.add(transcript)
            self._db.session.commit()
            logger.info("Added transcript to database")

        speaker_mapping = self._get_speaker_mapping(
            transcript.text,
            participants,
            meeting.meeting_id
        )
        logger.info("Inferred speaker mapping")
        transcript.speaker_mapping = json.dumps(speaker_mapping)
        if not self._debug_run:
            self._db.session.commit()
            logger.info("Added speaker mapping to database")

        for speaker, participant in speaker_mapping["speaker_mapping"].items():
            transcript.text = transcript.text.replace(speaker, participant)
        
        logger.info("Applied speaker mapping to transcript")
        if not self._debug_run:
            self._db.session.commit()
            logger.info("Updated transcript in database")

        logger.info("Waiting one minute to cool down anthropic API")
        if not self._debug_run:
            time.sleep(ANTROPIC_COOL_DOWN_SECONDS)

        agenda = self._infer_agenda(
            transcript.text,
            meeting.topic,
            meeting.meeting_id
        )
        logger.info("Inferred agenda")
        
        if not self._debug_run:
            self._db.session.add(agenda)
            self._db.session.commit()
            logger.info("Added agenda to database")

        logger.info("Waiting one minute to cool down anthropic API")
        if not self._debug_run:
            time.sleep(ANTROPIC_COOL_DOWN_SECONDS)

        meeting_protocol = self._create_meeting_protocol(
            transcript.text,
            agenda.text,
            meeting.date,
            meeting.meeting_id
        )
        logger.info("Created meeting protocol")
        meeting_protocol.status = "raw"
        
        if not self._debug_run:
            self._db.session.add(meeting_protocol)
            self._db.session.commit()
            logger.info("Added meeting protocol to database")

        logger.info("Waiting one minute to cool down anthropic API")
        if not self._debug_run:
            time.sleep(ANTROPIC_COOL_DOWN_SECONDS)

        filename = self._create_filename(
            meeting_protocol.text,
            meeting.date,
            meeting.meeting_id
        )
        logger.info("Created filename")
        
        language, translated_protocol = self._ensure_language(
            transcript.text,
            meeting_protocol.text,
            meeting.meeting_id
        )

        meeting_protocol.language = language
        meeting_protocol.text = translated_protocol
        meeting_protocol.status = "language ensured"
        logger.info("Ensured language")
        
        if not self._debug_run:
            self._db.session.commit()
            logger.info("Updated meeting protocol in database")

        meeting_protocol.text = self._ensure_markdown(
            meeting_protocol.text,
            meeting.meeting_id
        )
        meeting_protocol.status = "markdown ensured"
        logger.info("Ensured markdown")
        
        if not self._debug_run:
            self._db.session.commit()
            logger.info("Updated meeting protocol in database")
        
        drive_file_id, doc_url = export_to_google_drive(
            filename,
            meeting_protocol.text,
            participants
        )
        logger.info(f"Meeting protocol exported to Google Drive: {doc_url}")

        meeting_protocol.google_drive_file_id = drive_file_id
        meeting_protocol.google_drive_filename = filename
        meeting_protocol.google_drive_url = doc_url
        meeting_protocol.status = "exported to Google Drive"
        
        if not self._debug_run:
            self._db.session.commit()
            logger.info("Updated meeting protocol in database")

        return doc_url

    def _transcribe_audio(
        self,
        input_file_path: Union[str, Path],
        num_speakers: int,
        meeting_id: int
    ) -> aai.Transcript:
        if self._debug_run:
            cached_transcript = self._load_from_cache_if_exists(
                f"transcript_{meeting_id}"
            )
        
            if cached_transcript is not None:
                transcript = Transcripts(
                    meeting_id=meeting_id,
                    text=cached_transcript
                )
                return transcript

        is_wav = Path(input_file_path).suffix == ".wav"

        if is_wav:
            audio = AudioSegment.from_wav(input_file_path)
            audio.export("/tmp/output.mp3", format="mp3")
            input_file_path = "/tmp/output.mp3"

        transcript = self._transcriber.transcribe(
            data=str(input_file_path),
            config=aai.TranscriptionConfig(
                language_code="de",
                speaker_labels=True,
                speakers_expected=num_speakers,
                speech_model="best",
            ),
        )

        text = self._get_text_with_speaker_labels(transcript)

        if self._debug_run:
            self._save_to_cache(f"transcript_{meeting_id}", text)
        
        transcript = Transcripts(
            meeting_id=meeting_id,
            text=text
        )

        if is_wav:
            os.remove("/tmp/output.mp3")

        return transcript
    
    def _get_text_with_speaker_labels(
        self,
        transcript: aai.Transcript
    ) -> str:
        text_with_speaker_labels = ""

        for utt in transcript.utterances:
            text_with_speaker_labels += f"Speaker {utt.speaker}:\n{utt.text}\n"

        return text_with_speaker_labels
    
    def _get_speaker_mapping(
        self,
        transcript: str,
        participants: list[Participants],
        meeting_id: int
    ) -> dict:
        example_json = {
            "speaker_mapping": {
                "Speaker A": "Participant 1",
                "Speaker B": "Participant 2",
            }
        }

        prompt = PROMPTS["speaker_mapping"]["message"].format(
            participants=[p.name for p in participants],
            transcript=transcript,
            example_json=json.dumps(example_json)
        )

        message = self._call_claude_agent(
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
        if cache_key and self._debug_run:
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
        if cache_key and self._debug_run:
            self._save_to_cache(cache_key, result)
        
        return result

    def _load_from_cache_if_exists(
        self,
        key: str
    ) -> dict | None:
        if not self._debug_run:
            return None
        if os.path.exists(f"cache/{key}.pkl"):
            return pickle.load(open(f"cache/{key}.pkl", "rb"))
        return None

    def _save_to_cache(
        self,
        key: str,
        data: dict
    ) -> None:
        if not self._debug_run:
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
        agenda = Agendas(
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
        meeting_protocol = MeetingProtocols(
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

        translated_protocol = self._call_claude_agent(
            prompt,
            PROMPTS["ensure_language"]["system"],
            5000,
            cache_key=f"ensure_language_{meeting_id}"
        )

        return language, translated_protocol
    
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

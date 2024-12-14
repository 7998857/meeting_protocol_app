import logging

from app import db
from config import Config
from app.models import Participants, Meetings, Transcriptions, Protocols

from flask import copy_current_request_context
import os


from functools import wraps
from queue import Queue

logger = logging.getLogger(__name__)
logger.setLevel(Config.LOG_LEVEL)



import argparse
import os
import assemblyai as aai
from pydub import AudioSegment

aai.settings.api_key = Config.ASSEMBLYAI_API_KEY
transcriber = aai.Transcriber()


def create_meeting_protocol(
        input_file_path: str,
        prompt: str,
) -> str:
    if input_file_path.endswith(".wav"):
        audio = AudioSegment.from_wav(input_file_path)
        audio.export("/tmp/output.mp3", format="mp3")
        input_file_path = "/tmp/output.mp3"

    logger.info("Transcribing audio...")
    transcript = transcribe_audio(input_file_path)

    logger.info("Generating meeting protocol...")
    result = transcript.lemur.task(
        prompt, final_model=aai.LemurModel.claude3_5_sonnet
    )

    os.remove("/tmp/output.mp3")
    return result.response


def transcribe_audio(
        input_file_path: str,
        num_speakers: int = 4,
) -> str:
    transcript = transcriber.transcribe(
        data=input_file_path,
        config=aai.TranscriptionConfig(
            language_code="de",
            speaker_labels=True,
            speakers_expected=num_speakers,
            speech_model="best",
        ),
    )
    return transcript
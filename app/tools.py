import logging
import os

import assemblyai as aai
from pydub import AudioSegment

from app import db
from config import Config
from app.models import Meetings


logger = logging.getLogger(__name__)
logger.setLevel(Config.LOG_LEVEL)

aai.settings.api_key = Config.ASSEMBLYAI_API_KEY
transcriber = aai.Transcriber()


def summarize_meeting(
        transcript: aai.Transcript,
        prompt: str,
) -> str:
    logger.info("Generating meeting protocol...")
    result = transcript.lemur.task(
        prompt, final_model=aai.LemurModel.claude3_5_sonnet
    )
    return result.response


def transcribe_audio(
        input_file_path: str,
        num_speakers: int = 4,
) -> aai.Transcript:

    is_wav = input_file_path.endswith(".wav")

    if is_wav:
        audio = AudioSegment.from_wav(input_file_path)
        audio.export("/tmp/output.mp3", format="mp3")
        input_file_path = "/tmp/output.mp3"

    transcript = transcriber.transcribe(
        data=input_file_path,
        config=aai.TranscriptionConfig(
            language_code="de",
            speaker_labels=True,
            speakers_expected=num_speakers,
            speech_model="best",
        ),
    )

    if is_wav:
        os.remove("/tmp/output.mp3")

    return transcript

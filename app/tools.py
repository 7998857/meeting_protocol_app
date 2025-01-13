import logging
import os
from pathlib import Path
from typing import Union

import assemblyai as aai
from pydub import AudioSegment

from config import Config


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
        input_file_path: Union[str, Path],
        num_speakers: int = 4,
) -> aai.Transcript:

    is_wav = Path(input_file_path).suffix == ".wav"

    if is_wav:
        audio = AudioSegment.from_wav(input_file_path)
        audio.export("/tmp/output.mp3", format="mp3")
        input_file_path = "/tmp/output.mp3"

    transcript = transcriber.transcribe(
        data=str(input_file_path),
        config=aai.TranscriptionConfig(
            language_code="de",
            speaker_labels=True,
            speakers_expected=num_speakers,
            speech_model="best",
        ),
    )

    # transcript = add_speaker_labels(transcript)

    if is_wav:
        os.remove("/tmp/output.mp3")

    return transcript


def add_speaker_labels(transcript: aai.Transcript) -> aai.Transcript:
    text_with_speaker_labels = ""

    for utt in transcript.utterances:
        text_with_speaker_labels += f"Speaker {utt.speaker}:\n{utt.text}\n"
    # crashes like this because transcript.text has no setter
    transcript.text = text_with_speaker_labels

    return transcript

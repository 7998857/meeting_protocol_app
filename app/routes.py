from datetime import datetime
import logging
from pathlib import Path
import traceback

from flask import request, render_template, flash, redirect, url_for

from app import app, db
from app.models import Meetings, Participants, Transcriptions, \
                       Protocols, Prompts
from config import Config
from .tools import transcribe_audio, summarize_meeting, get_text_with_speaker_labels


logger = logging.getLogger(__name__)
logger.setLevel(Config.LOG_LEVEL)


@app.route("/", methods=["GET", "POST"])
def meeting_form():
    if request.method == "GET":
        # Get existing participants and prompts from database
        participants = Participants.query.all()
        prompts = Prompts.query.all()
        return render_template(
            "meeting_form.html",
            participants=participants,
            prompts=prompts,
            default_prompt=Config.DEFAULT_PROMPT
        )

    if request.method == "POST":
        try:
            meeting = Meetings(
                topic=request.form["topic"],
                date=datetime.strptime(
                    request.form["date"],
                    "%Y-%m-%dT%H:%M"
                )
            )
            db.session.add(meeting)
            db.session.commit()
        except Exception as e:
            # log error and traceback
            logger.error(f"Error creating new meeting: {str(e)}")
            logger.error(traceback.format_exc())
            flash("An error occurred while creating the meeting", "error")
            return redirect(url_for("meeting_form"))

        try:
            audio_file = request.files["audio_file"]
            extension = Path(audio_file.filename).suffix
            filepath = (
                Path(Config.UPLOAD_FOLDER) /
                f"{meeting.meeting_id}.{extension}"
            )
            audio_file.save(filepath)
        except Exception as e:
            # log error and traceback
            logger.error(f"Error uploading audio file: {str(e)}")
            logger.error(traceback.format_exc())
            flash(
                "An error occurred while uploading the audio file",
                "error"
            )
            return redirect(url_for("meeting_form"))

        try:
            meeting.audio_file_path = str(filepath)
            db.session.commit()
        except Exception as e:
            # log error and traceback
            logger.error(f"Error adding audio file path to meeting: {str(e)}")
            logger.error(traceback.format_exc())
            flash(
                "An error occurred while adding the audio path to the meeting",
                "error"
            )
            return redirect(url_for("meeting_form"))

        # Add participants to meeting
        try:
            participant_ids = request.form.getlist("participants")
            for participant_id in participant_ids:
                participant = Participants.query.get(participant_id)
                meeting.participants.append(participant)
            db.session.commit()
        except Exception as e:
            # log error and traceback
            logger.error(f"Error adding participants to meeting: {str(e)}")
            logger.error(traceback.format_exc())
            flash(
                "Error while adding the participants to the meeting",
                "error"
            )
            return redirect(url_for("meeting_form"))

        # Handle prompt
        try:
            prompt_text = request.form.get("prompt_text")

            if request.form.get("save_prompt"):
                new_prompt = Prompts(text=prompt_text)
                db.session.add(new_prompt)
                db.session.commit()
        except Exception as e:
            # log error and traceback
            logger.error(f"Error saving prompt: {str(e)}")
            logger.error(traceback.format_exc())
            flash("An error occurred while saving the prompt", "error")
            return redirect(url_for("meeting_form"))

        # Generate transcript
        try:
            logger.info(f"Transcribing audio file: {filepath}")
            flash(
                "Uploading and transcribing audio file. "
                "This may take a while...",
                "info"
            )
            transcript = transcribe_audio(
                filepath,
                num_speakers=len(participant_ids)
            )

            transcription = Transcriptions(
                meeting_id=meeting.meeting_id,
                text=get_text_with_speaker_labels(transcript)
            )
            db.session.add(transcription)
            db.session.commit()
        except Exception as e:
            # log error and traceback
            logger.error(f"Error generating transcript: {str(e)}")
            logger.error(traceback.format_exc())
            flash(
                "An error occurred while generating the transcript",
                "error"
            )
            return redirect(url_for("meeting_form"))

        # Generate protocol
        try:
            logger.info(f"Summarizing meeting with prompt: {prompt_text}")
            flash(
                "Summarizing meeting. This may take a while...",
                "info"
            )
            prompt_text += (
                f" Das Meeting wurde am {meeting.date.strftime('%d.%m.%Y um %H:%M')} "
                f"Uhr abgehalten. Das Thema der Sitzung war: {meeting.topic}. "
                "Die folgenden Teilnehmer waren anwesend: "
                f"{', '.join([participant.name for participant in meeting.participants])}"
            )

            protocol_text = summarize_meeting(
                get_text_with_speaker_labels(transcript),
                prompt_text
            )
            protocol = Protocols(
                meeting_id=meeting.meeting_id,
                transcription_id=transcription.transcription_id,
                text=protocol_text,
            )
            db.session.add(protocol)
            db.session.commit()
        except Exception as e:
            # log error and traceback
            logger.error(f"Error generating protocol: {str(e)}")
            logger.error(traceback.format_exc())
            flash(
                "An error occurred while generating the protocol",
                "error"
            )
            return redirect(url_for("meeting_form"))

        return render_template(
            "meeting_form.html",
            protocol=protocol_text,
            participants=Participants.query.all(),
            prompts=Prompts.query.all(),
            default_prompt=Config.DEFAULT_PROMPT
        )


@app.route("/add_participant", methods=["POST"])
def add_participant():
    try:
        new_participant_name = request.form.get("new_participant")
        if new_participant_name:
            new_participant = Participants(name=new_participant_name)
            db.session.add(new_participant)
            db.session.commit()
            flash(
                f"Successfully added participant: {new_participant_name}",
                "success"
            )
        return redirect(url_for("meeting_form"))
    except Exception as e:
        logger.error(f"Error adding participant: {str(e)}")
        flash("An error occurred while adding the participant", "error")
        return redirect(url_for("meeting_form"))

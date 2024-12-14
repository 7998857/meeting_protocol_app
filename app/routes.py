import logging

from app import app, db
from config import Config
from app.models import Meetings, Participants, Transcriptions, Protocols, Prompts
from .tools import create_meeting_protocol
from flask import request, render_template, flash, redirect, url_for
from datetime import datetime
from werkzeug.utils import secure_filename
import os

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
            prompts=prompts
        )

    if request.method == "POST":
        try:
            # Handle file upload
            audio_file = request.files["audio_file"]
            filename = secure_filename(audio_file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            audio_file.save(filepath)

            # Handle new participants
            new_participant_name = request.form.get("new_participant")
            if new_participant_name:
                new_participant = Participants(name=new_participant_name)
                db.session.add(new_participant)
                db.session.commit()

            # Create new meeting
            meeting = Meetings(
                topic=request.form["topic"],
                date=datetime.strptime(request.form["date"], "%Y-%m-%dT%H:%M"),
                audio_file_path=filepath
            )
            db.session.add(meeting)
            db.session.commit()

            # Add participants to meeting
            participant_ids = request.form.getlist("participants")
            for participant_id in participant_ids:
                participant = Participants.query.get(participant_id)
                meeting.participants.append(participant)

            # Handle prompt
            prompt_text = request.form.get("custom_prompt")
            if not prompt_text:
                prompt_text = Prompts.query.get(request.form["existing_prompt"]).text

            if request.form.get("save_prompt"):
                new_prompt = Prompts(text=prompt_text)
                db.session.add(new_prompt)

            db.session.commit()

            # Generate protocol
            protocol = create_meeting_protocol(meeting.id, prompt_text)

            return render_template(
                "meeting_form.html",
                protocol=protocol,
                participants=Participants.query.all(),
                prompts=Prompts.query.all()
            )

        except Exception as e:
            logger.error(f"Error processing meeting form: {str(e)}")
            flash("An error occurred while processing your request")
            return redirect(url_for("meeting_form"))

@app.route("/create_meeting_protocol", methods=["POST"])
def create_meeting_protocol_endpoint():
    data = request.json
    meeting_id = data["meeting_id"]
    prompt = data["prompt"]
    return create_meeting_protocol(meeting_id, prompt)

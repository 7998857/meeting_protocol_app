import os
from datetime import datetime
import logging
from pathlib import Path
import traceback

from flask import request, render_template, flash, redirect, url_for, jsonify

from app import app, db

from .models import Meetings, Participants, Transcripts, \
                       MeetingProtocols
from config import Config
from .meeting_audio_summarizer import MeetingAudioSummarizer
from flask_apscheduler import APScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore


logger = logging.getLogger(__name__)
logger.setLevel(Config.LOG_LEVEL)

# Initialize scheduler
scheduler = APScheduler()

# This function should be called in your app's __init__.py
def init_scheduler(app):
    # Configure scheduler to use SQLAlchemy for persistent job storage
    app.config['SCHEDULER_JOBSTORES'] = {
        'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])
    }
    app.config['SCHEDULER_API_ENABLED'] = True
    scheduler.init_app(app)
    scheduler.start()
    return scheduler

# Background job function
def process_meeting_summarization(meeting_id):
    with app.app_context():
        try:
            meeting = Meetings.query.get(meeting_id)
            if not meeting:
                logger.error(f"Meeting with ID {meeting_id} not found")
                return
                
            meeting.status = "processing"
            db.session.commit()
            
            summarizer = MeetingAudioSummarizer(db)
            doc_url = summarizer.summarize_meeting(meeting)
            
            # Update meeting status in database
            meeting.status = "completed"
            meeting.doc_url = doc_url
            db.session.commit()
            
            logger.info(f"Successfully processed meeting {meeting_id}, doc URL: {doc_url}")
        except Exception as e:
            logger.error(f"Error in background job: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update meeting status to failed
            try:
                meeting = Meetings.query.get(meeting_id)
                if meeting:
                    meeting.status = "failed"
                    db.session.commit()
            except Exception as inner_e:
                logger.error(f"Error updating meeting status: {str(inner_e)}")

@app.route("/", methods=["GET", "POST"])
def meeting_form():
    if request.method == "GET":
        # Get existing participants and prompts from database
        participants = Participants.query.all()
        # Get meetings with their status
        meetings = Meetings.query.order_by(Meetings.date.desc()).limit(5).all()
        return render_template(
            "meeting_form.html",
            participants=participants,
            meetings=meetings,
            now=datetime.now()
        )

    if request.method == "POST":
        try:
            debug_meeting_id = os.environ.get("DEBUG_MEETING_ID", None)
            if debug_meeting_id:
                meeting = Meetings.query.get(debug_meeting_id)
            else:
                meeting = Meetings(
                    topic=request.form["topic"],
                    date=datetime.strptime(
                        request.form["date"],
                        "%Y-%m-%dT%H:%M"
                    ),
                    status="pending"  # Add status field
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

        # Schedule the background job
        try:
            # Schedule the job to run immediately
            job_id = f"meeting_{meeting.meeting_id}"
            scheduler.add_job(
                id=job_id,
                func=process_meeting_summarization,
                args=[meeting.meeting_id],
                trigger='date',  # Run once immediately
                run_date=datetime.now(),
                replace_existing=True
            )
            
            meeting.job_id = job_id
            meeting.status = "scheduled"
            db.session.commit()
            
            flash(
                "Your meeting is being processed in the background. "
                "You can check the status on the meetings page.",
                "info"
            )
        except Exception as e:
            logger.error(f"Error scheduling background job: {str(e)}")
            logger.error(traceback.format_exc())
            flash(
                "An error occurred while scheduling the background process",
                "error"
            )

        return redirect(url_for("meeting_form"))


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

# Add a route to check job status
@app.route("/job_status/<job_id>")
def job_status(job_id):
    job = scheduler.get_job(job_id)
    if job:
        return jsonify({
            'id': job.id,
            'next_run_time': str(job.next_run_time) if job.next_run_time else None
        })
    else:
        # Job not found, check if it completed
        meeting = Meetings.query.filter_by(job_id=job_id).first()
        if meeting:
            return jsonify({
                'id': job_id,
                'status': meeting.status,
                'doc_url': meeting.doc_url if meeting.status == 'completed' else None
            })
        return jsonify({'error': 'Job not found'}), 404

import os
from datetime import datetime
import logging
from pathlib import Path
import traceback

from flask import request, render_template, flash, redirect, url_for, jsonify

from app import app, db

from .models import Meetings, Participants
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
        'default': SQLAlchemyJobStore(
            url=app.config['SQLALCHEMY_DATABASE_URI'],
            engine_options=Config.SQLALCHEMY_ENGINE_OPTIONS
        )
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
    db.create_all()
    if request.method == "GET":
        # Get existing participants and prompts from database
        participants = Participants.query.all()
        # Get meetings with their status
        meetings = Meetings.query.order_by(
            Meetings.created_at.desc()
        ).limit(5).all()
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
            if debug_meeting_id is None:
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
            if debug_meeting_id is None:
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


@app.route("/participants")
def participants():
    """Display the participants management page."""
    participants = Participants.query.order_by(Participants.name).all()
    return render_template("participants.html", participants=participants)


@app.route("/add_participant", methods=["POST"])
def add_participant():
    try:
        new_participant_name = request.form.get("new_participant")
        email = request.form.get("email")
        tag = request.form.get("tag")
        
        if new_participant_name and email:
            # Check if participant already exists
            existing = Participants.query.filter_by(name=new_participant_name).first()
            if existing:
                flash(f"Participant '{new_participant_name}' already exists", "error")
                return redirect(url_for("participants"))
                
            new_participant = Participants(
                name=new_participant_name,
                email=email.lower(),
                tag=tag if tag else None
            )
            db.session.add(new_participant)
            db.session.commit()
            
            # Handle audio sample upload
            audio_sample = request.files.get("audio_sample")
            if audio_sample and audio_sample.filename:
                try:
                    extension = Path(audio_sample.filename).suffix
                    filename = f"participant_{new_participant.participant_id}_{new_participant.name.replace(' ', '_')}{extension}"
                    filepath = Path(Config.AUDIO_SAMPLES_FOLDER) / filename
                    audio_sample.save(filepath)
                    
                    new_participant.audio_sample_file_path = str(filepath)
                    db.session.commit()
                except Exception as audio_e:
                    logger.error(f"Error saving audio sample: {str(audio_e)}")
                    flash("Participant added, but audio sample could not be saved", "warning")
            
            flash(
                f"Successfully added participant: {new_participant_name}",
                "success"
            )
        else:
            flash("Both name and email are required", "error")
            
        return redirect(url_for("participants"))
    except Exception as e:
        logger.error(f"Error adding participant: {str(e)}")
        flash("An error occurred while adding the participant", "error")
        return redirect(url_for("participants"))


@app.route("/update_participant/<int:participant_id>", methods=["POST"])
def update_participant(participant_id):
    try:
        participant = Participants.query.get_or_404(participant_id)
        
        name = request.form.get("name")
        email = request.form.get("email")
        tag = request.form.get("tag")
        
        if not name:
            flash("Participant name is required", "error")
            return redirect(url_for("participants"))
            
        # Check if another participant has the same name
        existing = Participants.query.filter(
            Participants.name == name,
            Participants.participant_id != participant_id
        ).first()
        if existing:
            flash(f"Another participant with name '{name}' already exists", "error")
            return redirect(url_for("participants"))
        
        participant.name = name
        participant.email = email.lower() if email else None
        participant.tag = tag if tag else None
        
        # Handle audio sample upload
        audio_sample = request.files.get("audio_sample")
        if audio_sample and audio_sample.filename:
            try:
                # Remove old audio sample if it exists
                if participant.audio_sample_file_path:
                    old_file = Path(participant.audio_sample_file_path)
                    if old_file.exists():
                        old_file.unlink()
                
                extension = Path(audio_sample.filename).suffix
                filename = f"participant_{participant_id}_{name.replace(' ', '_')}{extension}"
                filepath = Path(Config.AUDIO_SAMPLES_FOLDER) / filename
                audio_sample.save(filepath)
                
                participant.audio_sample_file_path = str(filepath)
            except Exception as audio_e:
                logger.error(f"Error updating audio sample: {str(audio_e)}")
                flash("Participant updated, but audio sample could not be saved", "warning")
        
        db.session.commit()
        flash(f"Successfully updated participant: {name}", "success")
        
    except Exception as e:
        logger.error(f"Error updating participant: {str(e)}")
        flash("An error occurred while updating the participant", "error")
        
    return redirect(url_for("participants"))


@app.route("/delete_participant/<int:participant_id>")
def delete_participant(participant_id):
    try:
        participant = Participants.query.get_or_404(participant_id)
        participant_name = participant.name
        
        # Check if participant is associated with any meetings
        if participant.meetings:
            flash(
                f"Cannot delete '{participant_name}' - participant is associated with existing meetings",
                "error"
            )
            return redirect(url_for("participants"))
        
        # Remove audio sample file if it exists
        if participant.audio_sample_file_path:
            try:
                audio_file = Path(participant.audio_sample_file_path)
                if audio_file.exists():
                    audio_file.unlink()
            except Exception as file_e:
                logger.error(f"Error removing audio file: {str(file_e)}")
        
        db.session.delete(participant)
        db.session.commit()
        flash(f"Successfully deleted participant: {participant_name}", "success")
        
    except Exception as e:
        logger.error(f"Error deleting participant: {str(e)}")
        flash("An error occurred while deleting the participant", "error")
        
    return redirect(url_for("participants"))


@app.route("/remove_audio_sample/<int:participant_id>")
def remove_audio_sample(participant_id):
    try:
        participant = Participants.query.get_or_404(participant_id)
        
        if participant.audio_sample_file_path:
            try:
                audio_file = Path(participant.audio_sample_file_path)
                if audio_file.exists():
                    audio_file.unlink()
            except Exception as file_e:
                logger.error(f"Error removing audio file: {str(file_e)}")
            
            participant.audio_sample_file_path = None
            db.session.commit()
            flash(f"Audio sample removed for {participant.name}", "success")
        else:
            flash("No audio sample to remove", "info")
            
    except Exception as e:
        logger.error(f"Error removing audio sample: {str(e)}")
        flash("An error occurred while removing the audio sample", "error")
        
    return redirect(url_for("participants"))


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

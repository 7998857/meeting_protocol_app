from datetime import datetime
from app import db


# association table for many-to-many relationship
# between meetings and participants
meeting_participants = db.Table(
    'meeting_participants',
    db.Column(
        'meeting_id',
        db.Integer,
        db.ForeignKey('meetings.meeting_id'),
        primary_key=True
    ),
    db.Column(
        'participant_id',
        db.Integer,
        db.ForeignKey('participants.participant_id'),
        primary_key=True
    )
)


class Participants(db.Model):
    participant_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True)
    email = db.Column(db.Text)
    audio_sample_file_path = db.Column(db.Text)
    tag = db.Column(db.Text)
    changed_at = db.Column(
        db.DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Add the relationship to meetings
    meetings = db.relationship(
        'Meetings',
        secondary=meeting_participants,
        backref=db.backref('participants', lazy='dynamic')
    )

    def __repr__(self):
        return f"<Participant {self.name}>"


class Meetings(db.Model):
    meeting_id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.Text)
    date = db.Column(db.DateTime)
    audio_file_path = db.Column(db.Text)
    language = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    job_id = db.Column(db.String(50), nullable=True)
    doc_url = db.Column(db.String(255), nullable=True)
    tag = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    changed_at = db.Column(
        db.DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )
    
    def __repr__(self):
        return f"<Meeting {self.topic} ({self.date})>"


class Transcripts(db.Model):
    transcript_id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(
        db.Integer,
        db.ForeignKey("meetings.meeting_id")
    )
    text = db.Column(db.Text)
    speaker_mapping = db.Column(db.Text)
    tag = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    changed_at = db.Column(
        db.DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )

    meeting = db.relationship("Meetings", backref="transcripts")

    def __repr__(self):
        return f"<Transcription {self.meeting_id}>"


class MeetingProtocols(db.Model):
    meeting_protocol_id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(
        db.Integer,
        db.ForeignKey("meetings.meeting_id")
    )
    transcript_id = db.Column(
        db.Integer,
        db.ForeignKey("transcripts.transcript_id")
    )
    text = db.Column(db.Text)
    google_drive_file_id = db.Column(db.Text)
    google_drive_filename = db.Column(db.Text)
    google_drive_url = db.Column(db.Text)
    status = db.Column(db.Text)
    tag = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    changed_at = db.Column(
        db.DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )

    meeting = db.relationship("Meetings", backref="meeting_protocols")

    def __repr__(self):
        return f"<MeetingProtocol {self.meeting_id}>"


class Agendas(db.Model):
    agenda_id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(
        db.Integer,
        db.ForeignKey("meetings.meeting_id")
    )
    text = db.Column(db.Text, nullable=False)
    tag = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    changed_at = db.Column(
        db.DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )
    
    meeting = db.relationship("Meetings", backref="agendas")

    def __repr__(self):
        return f"<Agenda {self.meeting_id}>"

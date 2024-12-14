from datetime import datetime
from app import app, db


class Prompts(db.Model):
    prompt_id = db.Column(db.Integer, primary_key=True, index=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, index=True, default=datetime.now)

    def __repr__(self):
        return f"<Prompt {self.text}>"


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
    participant_id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.Text, unique=True)
    changed_at = db.Column(db.DateTime, index=True, default=datetime.now)
    created_at = db.Column(db.DateTime, index=True, default=datetime.now)
    # Add the relationship to meetings
    meetings = db.relationship(
        'Meetings',
        secondary=meeting_participants,
        backref=db.backref('participants', lazy='dynamic')
    )

    def __repr__(self):
        return f"<Participant {self.name}>"


class Meetings(db.Model):
    meeting_id = db.Column(db.Integer, primary_key=True, index=True)
    topic = db.Column(db.Text)
    date = db.Column(db.DateTime, index=True)
    audio_file_path = db.Column(db.Text)
    created_at = db.Column(db.DateTime, index=True, default=datetime.now)
    # Remove the old participants relationship
    transcriptions = db.relationship(
        "Transcriptions", backref="meeting", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Meeting {self.topic} ({self.date})>"


class Transcriptions(db.Model):
    transcription_id = db.Column(db.Integer, primary_key=True, index=True)
    meeting_id = db.Column(
        db.Integer,
        db.ForeignKey("meetings.meeting_id"),
        index=True,
    )
    text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, index=True, default=datetime.now)

    def __repr__(self):
        return f"<Transcription {self.meeting_id}>"


class Protocols(db.Model):
    protocol_id = db.Column(db.Integer, primary_key=True, index=True)
    meeting_id = db.Column(
        db.Integer,
        db.ForeignKey("meetings.meeting_id"),
        index=True,
    )
    transcription_id = db.Column(
        db.Integer,
        db.ForeignKey("transcriptions.transcription_id"),
        index=True,
    )
    prompt_id = db.Column(
        db.Integer,
        db.ForeignKey("prompts.prompt_id"),
        index=True,
    )
    text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, index=True, default=datetime.now)

    def __repr__(self):
        return f"<Protocol {self.meeting_id}>"


# This creates the tables above if not already existing.
# Accordingly, it has to be done _after_ the definition of the Models!
with app.app_context():
    db.create_all()

import os

BASEDIR = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    """
    Basically just a namespace for the configuration.
    """

    # SCRIPT_NAME is gunicorn's env variable for path prefix
    PATH_PREFIX = os.environ.get("SCRIPT_NAME") or ""
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///"+os.path.join(BASEDIR, "database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LOG_LEVEL = os.environ.get("LOG_LEVEL") or "INFO"

    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "uploads"
    )

    # Create uploads directory if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")

    DEFAULT_PROMPT = (
        "Es handelt sich bei dem Gespräch um ein Arbeits-Meeting. "
        "Das Transkript wurde automatisch erstellt, es können sich also "
        "einige falsch erkannte Worte (insbesondere Zahlen) darin befinden. "
        "Bitte erstelle ein detailliertes Gesprächsprotokoll, das ich so am "
        "Ende den Gesprächsteilnehmern zusenden kann. Halte wenn möglich auch "
        "fest, wie die jeweiligen Teilnehmer zu den einzelnen Themen "
        "eingestellt sind. Bitte verwende das Markdown Format. Vielen Dank :)"
    )

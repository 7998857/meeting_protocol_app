import os

import dotenv

dotenv.load_dotenv()

BASEDIR = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    """
    Basically just a namespace for the configuration.
    """

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "postgresql://postgres:kaitos123@carne-truenas:10999/meeting_protocols"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    LOG_LEVEL = os.environ.get("LOG_LEVEL") or "INFO"

    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "uploads"
    )

    # Create uploads directory if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    ANTROPIC_COOL_DOWN_SECONDS = 120

    DEFAULT_PROMPT = (
        "Es handelt sich bei dem Gespräch um ein Arbeits-Meeting. "
        "Das Transkript wurde automatisch erstellt, es können sich also "
        "einige falsch erkannte Worte (insbesondere Zahlen) darin befinden. "
        "Bitte erstelle ein detailliertes Gesprächsprotokoll, das ich so am "
        "Ende den Gesprächsteilnehmern zusenden kann. Vielen Dank :)"
    )

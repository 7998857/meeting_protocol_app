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
    OCR_RETURN_CROP = int(os.environ.get("OCR_RETURN_CROP") or 1)
    OCR_RETURN_MASK = int(os.environ.get("OCR_RETURN_MASK") or 1)
    OCR_RETURN_PRED = int(os.environ.get("OCR_RETURN_PRED") or 1)
    TAGS = [f"crop={OCR_RETURN_CROP}",
            f"mask={OCR_RETURN_MASK}",
            f"decoded_predictions={OCR_RETURN_PRED}"]
    OCR_URL = os.environ.get("OCR_URL") or "http://carne-truenas:10000/ocr"
    OCR_URL += "?" + '&'.join(TAGS)
    MAX_OCR_CONNECTION_RETRIES = 4

    LOG_LEVEL = os.environ.get("LOG_LEVEL") or "INFO"

    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "uploads"
    )

    # Create uploads directory if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

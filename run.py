"""
run app on flask as webserver via
> python run.py
or
> flask run

run app on gunicorn as webserver via
> gunicorn --config=gunicorn_config.py run:app
"""

from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0")

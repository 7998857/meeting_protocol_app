FROM ubuntu:22.04

WORKDIR /usr/src/code

RUN apt-get update && apt-get dist-upgrade --no-install-recommends -y && apt-get install --no-install-recommends -y python3-pip python3-dev libturbojpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /usr/src/code
COPY requirements.txt /usr/src/code
RUN pip3 install -U pip
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . /usr/src/code

EXPOSE 5000

CMD ["gunicorn", "--config=gunicorn_config.py", "run:app"]
FROM python:3.8-slim-buster

WORKDIR /opt/app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
run pip3 install gunicorn[gevent]

COPY . .
EXPOSE 5000
ENV FLASK_APP=yodaspinbackend.py
ENV YODASPIN_SETTINGS=/opt/mnt/config.py

CMD gunicorn --worker-class gevent --workers 2 --bind 0.0.0.0:5000 wsgi:app --max-requests 10000 --timeout 5 --keep-alive 5 --log-level info
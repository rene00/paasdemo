FROM python:latest

ENV FLASK_APP app.py

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

CMD flask run --host=0.0.0.0 --port=8080

EXPOSE 8080

from flask import Flask, render_template, request
from sqlalchemy_utils import database_exists, create_database
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pytz
from sqlalchemy.exc import OperationalError
import boto3
import time
from botocore.exceptions import ClientError
import requests
import json
import logging

version = 1

service = os.environ.get('SERVICE')

mysql_username = os.environ.get('MYSQL_USERNAME')
mysql_password = os.environ.get('MYSQL_PASSWORD')
mysql_hostname = os.environ.get('MYSQL_HOSTNAME')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://{0}:{1}@{2}:3306/useragent'.
    format(mysql_username, mysql_password, mysql_hostname)
)
db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logging.getLogger('botocore').setLevel(logging.WARN)
logging.getLogger('boto3').setLevel(logging.WARN)
logging.getLogger('requests').setLevel(logging.WARN)
logging.getLogger('sqlalchemy').setLevel(logging.WARN)
logger = logging.getLogger(__name__)


def get_region():
    """Query metadata service and retrieve region."""
    url = 'http://169.254.169.254/latest/dynamic/instance-identity/document'
    region = None
    try:
        resp = requests.get(url, timeout=0.5)
        resp.raise_for_status()
        region = resp.json()['region']
    except (requests.exceptions.HTTPError,
            requests.exceptions.ReadTimeout,
            KeyError):
        logger.exception('Trying to access {0} failed'.format(url))
    finally:
        return region


REGION = get_region()


def s3_put(bucket, key, body):
    response = {}
    if bucket:
        client = boto3.client('s3')
        try:
            response = client.put_object(
                Body=body,
                Bucket=bucket,
                Key=key
            )['ResponseMetadata']
        except ClientError:
            pass
    return response


def sqs_send_message(queue_name, message):
    response = {}
    if queue_name:
        client = boto3.client('sqs', region_name=REGION)
        try:
            url = client.get_queue_url(QueueName=queue_name)['QueueUrl']
            response = client.send_message(
                QueueUrl=url, MessageBody=message
            )['ResponseMetadata']
        except ClientError:
            pass
    return response


def dbconnect():
    engine = db.engine
    connected = False
    try:
        if not database_exists(engine.url):
            create_database(engine.url)
    except OperationalError:
        pass
    else:
        db.create_all()
        connected = True
    return connected


def utcnow():
    return datetime.utcnow().replace(tzinfo=pytz.utc)


class UserAgent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    useragent = db.Column(db.String(128), nullable=False)
    date = db.Column(db.DateTime, default=utcnow)


@app.route('/', defaults={'path': None})
@app.route('/<path:path>')
def home(path):
    dbconnected = dbconnect()
    useragent = request.headers.get('User-Agent')
    useragents = []
    path = path
    if dbconnected:
        ua = UserAgent(useragent=useragent)
        db.session.add(ua)
        db.session.commit()
        useragents = UserAgent.query.order_by(UserAgent.id.desc()).all()[0:10]

    s3 = s3_put(
        bucket=os.environ.get('S3_BUCKET_MYBUCKET1'),
        key=str(((time.time() + 0.5) * 1000)),
        body=useragent
    )

    sqs = sqs_send_message(
        queue_name=os.environ.get('SQS_QUEUE_NAME_MYQUEUE1'),
        message=json.dumps({'useragent': useragent})
    )

    return render_template(
        'home.html', version=version, environ=os.environ,
        useragents=useragents, dbconnected=dbconnected,
        s3=s3, sqs=sqs, service=service, path=path, region=REGION
    )


if __name__ == '__main__':
    app.run(debug=False)

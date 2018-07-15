from flask import Flask, render_template, request
from sqlalchemy_utils import database_exists, create_database
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pytz
from sqlalchemy.exc import OperationalError

version = 1

mysql_username = os.environ.get('MYSQL_USERNAME')
mysql_password = os.environ.get('MYSQL_PASSWORD')
mysql_hostname = os.environ.get('MYSQL_HOSTNAME')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://{0}:{1}@{2}:3306/useragent'.
    format(mysql_username, mysql_password, mysql_hostname)
)
db = SQLAlchemy(app)


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


@app.route('/')
def home():
    dbconnected = dbconnect()
    useragents = []
    if dbconnected:
        ua = UserAgent(useragent=request.headers.get('User-Agent'))
        db.session.add(ua)
        db.session.commit()
        useragents = UserAgent.query.order_by(UserAgent.id.desc()).all()[0:30]

    return render_template(
        'home.html', version=version, environ=os.environ,
        useragents=useragents, dbconnected=dbconnected
    )


if __name__ == '__main__':
    app.run(debug=False)

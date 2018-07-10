from flask import Flask, render_template
import os

version = 3

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('home.html', version=version, environ=os.environ)


if __name__ == '__main__':
    app.run(debug=False)

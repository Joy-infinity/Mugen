"""
Protect a Flask app with Mugen in three lines.

Run:
    pip install flask
    python examples/flask_example.py

Then visit http://127.0.0.1:5000/ in a browser (you pass through to the real
app). Hit it with a bot-like client and you fall into the maze:
    curl -A python-requests http://127.0.0.1:5000/
"""

from flask import Flask

from mugen.detector import Detector
from mugen.middleware import MugenMiddleware

app = Flask(__name__)


@app.route("/")
def home():
    return "<h1>My real website</h1><p>Only humans should see this.</p>"


def _record(environ, verdict):
    ip = environ.get("REMOTE_ADDR", "?")
    print(f"[mugen] trapped {ip} score={verdict.score} {verdict.reasons}")


# Wrap the WSGI app. That's it.
app.wsgi_app = MugenMiddleware(
    app.wsgi_app,
    detector=Detector(threshold=5),
    on_trap=_record,
)

if __name__ == "__main__":
    app.run(port=5000)

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
app.config["SQLALCHEMY_BINDS"] = {"other": "sqlite://"}
db = SQLAlchemy(app)


class Main(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))


class Other(db.Model):
    __bind_key__ = "other"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(20))


with app.app_context():
    db.create_all()
    db.session.add(Main(name="m1"))
    db.session.add(Other(label="o1"))
    db.session.add(Other(label="o2"))
    db.session.commit()


@app.route("/counts")
def counts():
    return jsonify({"main": Main.query.count(), "other": Other.query.count(), "o": [o.label for o in Other.query.order_by(Other.id)]})

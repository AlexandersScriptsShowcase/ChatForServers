import os
from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# Use environment variables for secret key and database URL (fallback to defaults)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///chat.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Use gevent async mode instead of eventlet
socketio = SocketIO(app, async_mode='gevent')

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # hashed password

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    content = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Flask CLI command to initialize DB
@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database initialized.")

# Favicon route
@app.route('/siteicon.ico')
def favicon():
    return send_from_directory('.', 'siteicon.ico')

# Routes
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["username"] = username
            return redirect("/chat")
        return "Invalid login"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if User.query.filter_by(username=username).first():
            return "Username already exists"
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect("/")
    return render_template("register.html")

@app.route("/chat")
def chat():
    if "username" not in session:
        return redirect("/")
    messages = Message.query.order_by(Message.timestamp).all()
    return render_template("chat.html", username=session["username"], messages=messages)

@app.route("/clear_chat", methods=["POST"])
def clear_chat():
    if "username" not in session or session["username"] != "IAmAlexAndStuff":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    Message.query.delete()
    db.session.commit()
    socketio.emit("chat_cleared")
    return jsonify({"status": "success"})

@app.route("/remove_message", methods=["POST"])
def remove_message():
    if "username" not in session or session["username"] != "aq":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    msg_id = request.json.get("id")
    reason = request.json.get("reason", "no reason")
    msg = Message.query.get(msg_id)
    if msg:
        username = msg.username
        db.session.delete(msg)
        db.session.commit()
        socketio.emit("message_removed", {"id": msg_id, "user": username, "reason": reason})
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Message not found"}), 404

@socketio.on("send_message")
def handle_message(data):
    new_msg = Message(username=data["user"], content=data["message"])
    db.session.add(new_msg)
    db.session.commit()
    emit("receive_message", {"id": new_msg.id, "user": data["user"], "message": data["message"]}, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
import os
import io
import traceback

import whisper
from transformers import pipeline
from deep_translator import GoogleTranslator
from fpdf import FPDF

import database  # FIXED database.py with absolute path

# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"mp3", "wav"}

# FFmpeg path (change only if needed)
os.environ["PATH"] += os.pathsep + r"C:\Users\Lenovo\Downloads\ffmpeg-8.0.1-essentials_build\ffmpeg-8.0.1-essentials_build\bin"

# Initialize database (ONE TIME, ONE DB)
database.init_db()

# ---------------- MODELS ----------------
print("Loading Whisper model...")
asr_model = whisper.load_model("base")
print("Whisper loaded")

print("Loading summarization model...")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
print("Summarizer loaded")

# ---------------- HELPERS ----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_summary(text):
    if len(text.split()) < 60:
        return text

    max_chunk_words = 450
    words = text.split()

    chunks = [
        " ".join(words[i:i + max_chunk_words])
        for i in range(0, len(words), max_chunk_words)
    ]

    summaries = []
    for chunk in chunks:
        summary = summarizer(
            chunk,
            max_length=150,
            min_length=60,
            do_sample=False
        )[0]["summary_text"]
        summaries.append(summary)

    return " ".join(summaries)

# ---------------- AUTH ROUTES ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        conn = database.get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        conn.close()

        if not user:
            return render_template("login.html", error="Email not registered")

        if user["password"] != password:
            return render_template("login.html", error="Incorrect password")

        session["user"] = email
        return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        conn = database.get_db()

        existing = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            return render_template("reg.html", error="Email already exists")

        conn.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("reg.html")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        conn = database.get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        conn.close()

        if user:
            return render_template("forgotpass.html", success="Password reset link sent (demo)")
        else:
            return render_template("forgotpass.html", error="Email not registered")

    return render_template("forgotpass.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ---------------- MAIN APP ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("index.html")

    try:
        if "audio" not in request.files:
            return jsonify({"error": "No file selected"})

        file = request.files["audio"]

        if file.filename == "":
            return jsonify({"error": "No file selected"})

        if not allowed_file(file.filename):
            return jsonify({"error": "Only MP3 or WAV files allowed"})

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        # Transcription
        result = asr_model.transcribe(filepath)
        transcription = result.get("text", "").strip()

        if transcription == "":
            transcription = "No clear speech detected."

        # Summary
        summary = generate_summary(transcription)

        return jsonify({
            "transcript": transcription,
            "summary": summary
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})

# ---------------- TRANSLATION ----------------
@app.route("/translate", methods=["POST"])
def translate_text():
    data = request.json
    content = data.get("content", "")
    lang = data.get("lang", "en")

    if lang != "en":
        translated = GoogleTranslator(source="auto", target=lang).translate(content)
    else:
        translated = content

    return jsonify({"translated": translated})

# ---------------- DOWNLOAD TXT ----------------
@app.route("/download/txt")
def download_txt():
    content = request.args.get("content", "")
    type_file = request.args.get("type", "transcript")
    lang = request.args.get("lang", "en")

    return send_file(
        io.BytesIO(content.encode("utf-8")),
        as_attachment=True,
        download_name=f"{type_file}_{lang}.txt",
        mimetype="text/plain"
    )

# ---------------- DOWNLOAD PDF ----------------
@app.route("/download/pdf")
def download_pdf():
    content = request.args.get("content", "")
    type_file = request.args.get("type", "transcript")
    lang = request.args.get("lang", "en")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for line in content.split("\n"):
        pdf.multi_cell(0, 8, line)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=f"{type_file}_{lang}.pdf",
        mimetype="application/pdf"
    )

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)

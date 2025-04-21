from flask import Flask, render_template, request, redirect, url_for
import json
import os
from models.topic_alignment import get_alignment_score
from models.doubt_detection import detect_doubt

app = Flask(__name__)

# Load learning objectives
with open("data/learning_objectives.txt", "r") as f:
    LEARNING_OBJECTIVES = [line.strip() for line in f.readlines()]

# Load question bank
with open("data/question_bank.json", "r") as f:
    QUESTION_BANK = json.load(f)

@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")

@app.route("/analyze", methods=["GET", "POST"])
def analyze():
    if request.method == "POST":
        journal_text = request.form.get("journal")
        
        # Calculate alignment scores
        alignment_scores = get_alignment_score(journal_text, LEARNING_OBJECTIVES)
        
        # Detect doubt
        doubt_label = detect_doubt(journal_text)
        
        # Store results in session or pass via URL (for simplicity, we use URL params)
        return redirect(url_for("result", alignment_scores=json.dumps(alignment_scores), doubt_label=doubt_label))
    
    return render_template("analyze.html")

@app.route("/result", methods=["GET"])
def result():
    alignment_scores = json.loads(request.args.get("alignment_scores"))
    doubt_label = request.args.get("doubt_label")
    return render_template("result.html", alignment_scores=alignment_scores, doubt_label=doubt_label)

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if request.method == "POST":
        user_answers = {key: value for key, value in request.form.items()}
        feedback = {}
        
        # Fetch correct answers from question bank
        for q_id, answer in user_answers.items():
            correct_answer = QUESTION_BANK[q_id]["correct"]
            feedback[q_id] = {
                "user_answer": answer,
                "correct_answer": correct_answer,
                "is_correct": answer == correct_answer
            }
        
        return render_template("quiz_feedback.html", feedback=feedback)
    
    # Fetch weak topics (simulated here; in practice, derive from alignment scores)
    weak_topics = ["LO_1", "LO_3"]  # Example weak topics
    questions = {topic: QUESTION_BANK[topic] for topic in weak_topics if topic in QUESTION_BANK}
    return render_template("quiz.html", questions=questions)


if __name__ == "__main__":
    app.run(debug=True)
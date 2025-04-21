# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import random
import numpy as np
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///adaptive_learning.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    responses = db.relationship('UserResponse', backref='user', lazy=True)
    skills = db.relationship('UserSkill', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    questions = db.relationship('Question', backref='topic', lazy=True)
    
    def __repr__(self):
        return f'<Topic {self.name}>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Float, nullable=False)  # 0 to 1, where 1 is most difficult
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    options = db.relationship('Option', backref='question', lazy=True)
    responses = db.relationship('UserResponse', backref='question', lazy=True)
    
    def __repr__(self):
        return f'<Question {self.id}>'

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    
    def __repr__(self):
        return f'<Option {self.id}>'

class UserResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('option.id'), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserResponse {self.id}>'

class UserSkill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    skill_level = db.Column(db.Float, nullable=False, default=0.5)  # 0 to 1
    
    def __repr__(self):
        return f'<UserSkill {self.id}>'

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user_exists = User.query.filter_by(username=username).first()
        
        if user_exists:
            return render_template('register.html', error='Username already exists')
        
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        # Initialize skills for new user
        topics = Topic.query.all()
        for topic in topics:
            new_skill = UserSkill(user_id=new_user.id, topic_id=topic.id, skill_level=0.5)
            db.session.add(new_skill)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    topics = Topic.query.all()
    
    # Get user skills for each topic
    user_skills = {}
    for topic in topics:
        skill = UserSkill.query.filter_by(user_id=user_id, topic_id=topic.id).first()
        if skill:
            user_skills[topic.id] = skill.skill_level * 100  # Convert to percentage
        else:
            user_skills[topic.id] = 50  # Default to 50%
    
    # Get recent performance
    recent_responses = UserResponse.query.filter_by(user_id=user_id).order_by(UserResponse.timestamp.desc()).limit(10).all()
    correct_count = sum(1 for response in recent_responses if response.is_correct)
    recent_performance = (correct_count / len(recent_responses) * 100) if recent_responses else 0
    
    return render_template('dashboard.html', 
                          user=user, 
                          topics=topics, 
                          user_skills=user_skills, 
                          recent_performance=recent_performance)

@app.route('/quiz/<int:topic_id>')
def quiz(topic_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    topic = Topic.query.get(topic_id)
    
    if not topic:
        return redirect(url_for('dashboard'))
    
    # Get user's skill level for this topic
    user_skill = UserSkill.query.filter_by(user_id=user_id, topic_id=topic_id).first()
    if not user_skill:
        user_skill = UserSkill(user_id=user_id, topic_id=topic_id, skill_level=0.5)
        db.session.add(user_skill)
        db.session.commit()
    
    # Select a question based on the user's skill level (adaptive)
    selected_question = select_appropriate_question(user_id, topic_id, user_skill.skill_level)
    
    if not selected_question:
        return render_template('no_questions.html', topic=topic)
    
    # Randomize option order
    options = list(selected_question.options)
    random.shuffle(options)
    
    return render_template('quiz.html', 
                          topic=topic, 
                          question=selected_question, 
                          options=options)

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    question_id = int(request.form['question_id'])
    option_id = int(request.form['option_id'])
    topic_id = int(request.form['topic_id'])
    
    # Get selected option and check if it's correct
    selected_option = Option.query.get(option_id)
    is_correct = selected_option.is_correct
    
    # Record user's response
    user_response = UserResponse(
        user_id=user_id,
        question_id=question_id,
        option_id=option_id,
        is_correct=is_correct
    )
    db.session.add(user_response)
    
    # Update user's skill level for this topic
    update_skill_level(user_id, topic_id, is_correct)
    
    db.session.commit()
    
    # Return to quiz with feedback
    return render_template('answer_feedback.html', 
                          is_correct=is_correct, 
                          topic_id=topic_id,
                          explanation="Explanation would be provided here based on the answer.")

# AI Helper Functions
def select_appropriate_question(user_id, topic_id, skill_level):
    """
    Select a question appropriate for the user's skill level.
    Uses a probabilistic approach with some exploration.
    """
    # Get questions for this topic
    topic_questions = Question.query.filter_by(topic_id=topic_id).all()
    
    if not topic_questions:
        return None
    
    # Get questions the user has already answered
    answered_question_ids = [r.question_id for r in UserResponse.query.filter_by(user_id=user_id).all()]
    
    # Filter out questions the user has already answered, if possible
    unanswered_questions = [q for q in topic_questions if q.id not in answered_question_ids]
    
    # If all questions have been answered, allow repeats
    candidate_questions = unanswered_questions if unanswered_questions else topic_questions
    
    # Calculate probability of selecting each question based on difficulty
    # We want questions close to the user's skill level, with some exploration
    probs = []
    for question in candidate_questions:
        # Distance between question difficulty and user skill level
        distance = abs(question.difficulty - skill_level)
        # Convert to probability (closer = higher probability)
        # Add small exploration factor
        prob = np.exp(-5 * distance) + 0.1
        probs.append(prob)
    
    # Normalize probabilities
    probs = np.array(probs) / sum(probs)
    
    # Select a question based on the probabilities
    selected_index = np.random.choice(len(candidate_questions), p=probs)
    return candidate_questions[selected_index]

def update_skill_level(user_id, topic_id, is_correct):
    """
    Update the user's skill level for a topic based on their answer.
    """
    user_skill = UserSkill.query.filter_by(user_id=user_id, topic_id=topic_id).first()
    
    if not user_skill:
        user_skill = UserSkill(user_id=user_id, topic_id=topic_id, skill_level=0.5)
        db.session.add(user_skill)
    
    # Update skill level using a simple Bayesian approach
    # Correct answers increase skill level, incorrect answers decrease it
    # The magnitude decreases as more questions are answered
    
    # Get count of previous responses for this topic
    response_count = UserResponse.query.join(Question).filter(
        UserResponse.user_id == user_id,
        Question.topic_id == topic_id
    ).count()
    
    # Learning rate decreases with more responses
    learning_rate = 0.1 / (1 + 0.05 * response_count)
    
    if is_correct:
        # Increase skill level
        user_skill.skill_level = min(1.0, user_skill.skill_level + learning_rate * (1 - user_skill.skill_level))
    else:
        # Decrease skill level
        user_skill.skill_level = max(0.0, user_skill.skill_level - learning_rate * user_skill.skill_level)

# Admin routes for creating content
@app.route('/admin')
def admin():
    if 'user_id' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))
    
    topics = Topic.query.all()
    return render_template('admin.html', topics=topics)

@app.route('/admin/add_topic', methods=['POST'])
def add_topic():
    if 'user_id' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))
    
    topic_name = request.form['topic_name']
    
    new_topic = Topic(name=topic_name)
    db.session.add(new_topic)
    db.session.commit()
    
    return redirect(url_for('admin'))

@app.route('/admin/add_question/<int:topic_id>', methods=['GET', 'POST'])
def add_question(topic_id):
    if 'user_id' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))
    
    topic = Topic.query.get(topic_id)
    
    if request.method == 'POST':
        question_text = request.form['question_text']
        difficulty = float(request.form['difficulty'])
        
        new_question = Question(text=question_text, difficulty=difficulty, topic_id=topic_id)
        db.session.add(new_question)
        db.session.commit()
        
        # Add options
        for i in range(1, 5):  # Assuming 4 options
            option_text = request.form[f'option_{i}']
            is_correct = 'correct_option' in request.form and int(request.form['correct_option']) == i
            
            new_option = Option(text=option_text, is_correct=is_correct, question_id=new_question.id)
            db.session.add(new_option)
        
        db.session.commit()
        return redirect(url_for('admin'))
    
    return render_template('add_question.html', topic=topic)

# Create database tables
with app.app_context():
    db.create_all()
    
    # Add admin user if it doesn't exist
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', password='admin123')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'temp-secret-key-for-demo'

# Course data
COURSES = {
    'master': {'name': 'Master of all tools AI', 'price': 999},
    'python': {'name': 'Python for AI', 'price': None},
    'ml': {'name': 'Machine Learning in Depth', 'price': None},
    'nlp-dl': {'name': 'NLP & Deep Learning', 'price': None},
    'gen-ai': {'name': 'Generative AI Mastery', 'price': None},
}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    # Mock user data for demo
    mock_user = {'username': 'Demo User', 'payments': []}
    return render_template('dashboard.html', user=mock_user, COURSES=COURSES)

@app.route('/create_order', methods=['POST'])
def create_order():
    # Mock response for demo
    return jsonify({
        'order_id': 'demo_order_123',
        'amount': 99900,
        'currency': 'INR',
        'key_id': 'demo_key',
        'course_name': 'Master of all tools AI',
        'description': 'AITOOLS - Online Course'
    })

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    # Mock successful payment for demo
    return jsonify({'status': 'success', 'message': 'Payment verified successfully! (Demo Mode)'})

if __name__ == '__main__':
    app.run(debug=True, port=5001)

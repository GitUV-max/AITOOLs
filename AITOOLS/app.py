import os
import razorpay
import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
app.config['RAZORPAY_KEY_ID'] = os.getenv('RAZORPAY_KEY_ID')
app.config['RAZORPAY_KEY_SECRET'] = os.getenv('RAZORPAY_KEY_SECRET')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

# --- Initializations ---
db = SQLAlchemy(app)
razorpay_client = razorpay.Client(
    auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET'])
)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    course_id = db.Column(db.String(50), nullable=False)
    razorpay_order_id = db.Column(db.String(100), unique=True, nullable=False)
    razorpay_payment_id = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    user = db.relationship('User', backref=db.backref('payments', lazy=True))

# --- CLI Commands ---
@app.cli.command('init-db')
def init_db_command():
    """Creates the database tables."""
    with app.app_context():
        db.create_all()
    print('Initialized the database.')

# --- Course Data ---
COURSES = {
    'master': {'name': 'All-in-One AI Master Course', 'price': 999},
    'python': {'name': 'Python for AI & ML', 'price': 499},
    'ml': {'name': 'Machine Learning in Depth', 'price': 799},
    'nlp-dl': {'name': 'NLP & Deep Learning', 'price': 999},
    'gen-ai': {'name': 'Generative AI Mastery', 'price': 1499},
}

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_order', methods=['POST'])
def create_order():
    data = request.get_json()
    course_id = data.get('course_id')
    if not course_id or course_id not in COURSES:
        return jsonify({'error': 'Invalid course ID'}), 400

    course = COURSES[course_id]
    amount_in_paise = int(course['price'] * 100)

    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': f'receipt_{course_id}_{os.urandom(4).hex()}',
        'notes': {
            'course_id': course_id,
            'course_name': course['name']
        }
    }
    try:
        order = razorpay_client.order.create(data=order_data)
        return jsonify({
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'key_id': app.config['RAZORPAY_KEY_ID'],
            'course_name': course['name'],
            'description': 'AITOOLS - Online Course'
        })
    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({'error': 'Could not create order'}), 500

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    data = request.get_json()
    try:
        params_dict = {
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        }
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Payment is verified, now save to DB
        order_id = data['razorpay_order_id']
        payment_id = data['razorpay_payment_id']

        # You might want to fetch course_id and amount from your session or a temporary store
        # For now, we'll retrieve it from the order notes if possible
        order_details = razorpay_client.order.fetch(order_id)
        course_id = order_details['notes']['course_id']
        amount = order_details['amount']

        new_payment = Payment(
            user_id=session.get('user_id'), # This will be None if user is not logged in
            course_id=course_id,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            amount=amount,
            status='success'
        )
        db.session.add(new_payment)
        db.session.commit()

        print(f"SUCCESS: Payment for order {order_id} verified and saved.")
        return jsonify({'status': 'success', 'message': 'Payment verified successfully!'})

    except razorpay.errors.SignatureVerificationError as e:
        print(f"ERROR: Signature verification failed! {e}")
        return jsonify({'status': 'error', 'message': 'Payment verification failed.'}), 400
    except Exception as e:
        print(f"SERVER ERROR: {e}")
        # Also, save the failed payment attempt for auditing
        new_payment = Payment(
            user_id=session.get('user_id'),
            course_id=data.get('course_id', 'unknown'),
            razorpay_order_id=data.get('razorpay_order_id'),
            razorpay_payment_id=data.get('razorpay_payment_id'),
            amount=0, # Amount might not be available
            status='failed'
        )
        db.session.add(new_payment)
        db.session.commit()
        return jsonify({'status': 'error', 'message': 'An internal error occurred.'}), 500

# --- Auth Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        user_by_username = User.query.filter_by(username=username).first()
        user_by_email = User.query.filter_by(email=email).first()

        if user_by_username:
            flash('Username already exists.')
            return redirect(url_for('register'))
        if user_by_email:
            flash('Email already registered.')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You need to be logged in to view this page.')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    # Pass courses to the template so we can display course names from IDs
    return render_template('dashboard.html', user=user, COURSES=COURSES)


if __name__ == '__main__':
    app.run(debug=True, port=5001)

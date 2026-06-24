from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, make_response, jsonify
from dotenv import load_dotenv
import os
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps

load_dotenv()

from models import SessionLocal, User, Job

app = Flask(__name__)
app.secret_key = os.getenv('JWT_SECRET', 'supersecretkey')

JWT_SECRET = os.getenv('JWT_SECRET', 'supersecretkey')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24


# ─── JWT HELPERS ─────────────────────────────────────────────

def generate_token(email):
    """Generate a JWT token for the given email."""
    payload = {
        'email': email,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token):
    """Decode a JWT token and return the payload, or None if invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user():
    """Get the current user's email from the JWT cookie, or None."""
    token = request.cookies.get('auth_token')
    if not token:
        return None
    payload = decode_token(token)
    if payload:
        return payload.get('email')
    return None


def login_required(f):
    """Decorator to protect routes that require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_email = get_current_user()
        if not user_email:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─── CONTEXT PROCESSOR ──────────────────────────────────────

@app.context_processor
def inject_user():
    """Make current_user available in all templates."""
    email = get_current_user()
    return {
        'current_user': email,
        'user_initial': email[0].upper() if email else None
    }


# ─── ROUTES ─────────────────────────────────────────────────

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = os.path.join(app.root_path, 'assets')
    return send_from_directory(assets_dir, filename)


hero_slides = [
    {
        "eyebrow": "AI-Powered Platform",
        "heading": "Find Your<br>Next Role.",
        "body": "AI-powered job matching connects you with the right opportunities every day — curated precisely to your skills and goals.",
        "ctas": [
            {"text": "Explore Jobs &nbsp;→", "href": "/jobs", "class": "btn-primary"},
            {"text": "Upload Resume", "class": "btn-outline"}
        ]
    },
    {
        "eyebrow": "For Employers",
        "heading": "Hire With<br>Precision.",
        "body": "Thousands of leading companies rely on our platform to find top talent quickly and confidently.",
        "ctas": [
            {"text": "Post a Job &nbsp;→", "class": "btn-primary"},
            {"text": "View Packages", "class": "btn-outline"}
        ]
    },
    {
        "eyebrow": "Career Growth",
        "heading": "Curated<br>For You.",
        "body": "Receive daily alerts tailored to your profile. Your next career move is closer than you think.",
        "ctas": [
            {"text": "Create Profile &nbsp;→", "class": "btn-primary"},
            {"text": "Browse All", "class": "btn-outline"}
        ]
    },
    {
        "eyebrow": "Trusted Network",
        "heading": "98% Placement<br>Rate.",
        "body": "Our record speaks for itself. Join over 10,000 professionals who've landed their ideal role through our platform.",
        "ctas": [
            {"text": "Get Started &nbsp;→", "class": "btn-primary"},
            {"text": "View Stories", "class": "btn-outline"}
        ]
    }
]

@app.route('/')
def home():
    return render_template('index.html', hero_slides=hero_slides)


AI_Job_recommendation = [
    {
        "title": "Senior AI Engineer",
        "location": "Remote",
        "salary": "$140k - $180k",
        "type": "Full-time"
    },
    {
        "title": "Product Designer",
        "location": "New York, NY",
        "salary": "$110k - $150k",
        "type": "Full-time"
    },
    {
        "title": "Frontend Developer (React)",
        "location": "Remote",
        "salary": "$90k - $130k",
        "type": "Contract"
    },
    {
        "title": "Data Scientists",
        "location": "London, UK",
        "salary": "£70k - £90k",
        "type": "Full-time"
    }
]


@app.route('/about')
def about():
    return render_template('about.html')


def get_all_jobs():
    """Fetch all jobs from the database, newest first. Falls back to hardcoded list if DB is empty."""
    db = SessionLocal()
    try:
        db_jobs = db.query(Job).order_by(Job.created_at.desc()).all()
        if db_jobs:
            return [j.to_dict() for j in db_jobs]
        return AI_Job_recommendation
    finally:
        db.close()


@app.route('/jobs')
def jobs():
    return render_template('jobs.html', jobs=get_all_jobs())

@app.route('/job-board')
def job_board():
    return render_template('job_board.html', jobs=get_all_jobs())


@app.route('/add-job', methods=['GET', 'POST'])
@login_required
def add_job():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        company = request.form.get('company', '').strip()
        location = request.form.get('location', '').strip()
        salary = request.form.get('salary', '').strip()
        job_type = request.form.get('job_type', 'Full-time').strip()
        description = request.form.get('description', '').strip()

        # Validation
        if not title or not company or not location:
            flash('Title, Company, and Location are required.', 'error')
            return render_template('add_job.html')

        db = SessionLocal()
        try:
            job = Job(
                title=title,
                company=company,
                location=location,
                salary=salary or None,
                job_type=job_type,
                description=description or None,
                posted_by=get_current_user()
            )
            db.add(job)
            db.commit()
            flash('Job posted successfully!', 'success')
            return redirect(url_for('jobs'))
        except Exception:
            db.rollback()
            flash('Something went wrong. Please try again.', 'error')
            return render_template('add_job.html')
        finally:
            db.close()

    return render_template('add_job.html')



@app.route('/personalized-jobs')
@login_required
def personalized_jobs():
    return render_template('personalized_jobs.html')

@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    data = request.get_json()
    user_msg = data.get('message', '').lower()

    # Simple simulated AI matching logic
    all_jobs = get_all_jobs()
    matched_jobs = []

    # Try to find jobs matching keywords in the message
    for job in all_jobs:
        if (job.get('title') and job['title'].lower() in user_msg) or \
           (job.get('location') and job['location'].lower() in user_msg) or \
           (job.get('type') and job['type'].lower() in user_msg) or \
           (job.get('company') and job['company'].lower() in user_msg) or \
           (job.get('description') and job['description'].lower() in user_msg):
            matched_jobs.append(job)

    # Fallback to AI dummy data if no specific match
    if not matched_jobs:
        matched_jobs = AI_Job_recommendation[:2] # Return top 2 recommendations
        reply = "I've analyzed your profile and found these great opportunities that align with your skills:"
    else:
        reply = f"I found {len(matched_jobs)} job(s) that match your description. Here are the top matches:"

    return jsonify({
        'reply': reply,
        'jobs': matched_jobs
    })


# ─── AUTH ROUTES ─────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('login.html')

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user or not user.check_password(password):
                flash('Invalid email or password.', 'error')
                return render_template('login.html')

            # Generate JWT and set cookie
            token = generate_token(email)
            response = make_response(redirect(url_for('home')))
            response.set_cookie(
                'auth_token', token,
                httponly=True,
                max_age=JWT_EXPIRATION_HOURS * 3600,
                samesite='Lax'
            )
            return response
        finally:
            db.close()

    return render_template('login.html')


@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not email or not password:
        flash('Please fill in all fields.', 'error')
        return redirect(url_for('login'))

    if len(password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('login'))

    db = SessionLocal()
    try:
        # Check if user already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('login'))

        # Create new user
        user = User(email=email)
        user.set_password(password)
        db.add(user)
        db.commit()

        # Generate JWT and set cookie
        token = generate_token(email)
        response = make_response(redirect(url_for('home')))
        response.set_cookie(
            'auth_token', token,
            httponly=True,
            max_age=JWT_EXPIRATION_HOURS * 3600,
            samesite='Lax'
        )
        return response
    except Exception as e:
        db.rollback()
        flash('Something went wrong. Please try again.', 'error')
        return redirect(url_for('login'))
    finally:
        db.close()


@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('home')))
    response.delete_cookie('auth_token')
    return response


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

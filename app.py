
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, make_response
import os
import psycopg2
import jwt
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = os.path.join(app.root_path, 'assets')
    return send_from_directory(assets_dir, filename)

app.secret_key = 'supersecretkey' # Required for flashing messages


# Database connection function
def get_db_connection():
    # Since we are using a connection pooler from Supabase, make sure sslmode is configured
    conn = psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require')
    return conn


# Initialize DB
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

# Note: In a real app we might use a try-except, but for testing we'll assume it works if we can connect
try:
    init_db()
except Exception as e:
    print(f"Failed to initialize database: {e}")

# Helper function to get current user from token
def get_current_user():
    token = request.cookies.get('jwt_token')
    if not token:
        return None
    try:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return payload.get('email')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# Override app route inject
@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())



@app.route('/')
def home():
    return render_template('index.html')

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

@app.route('/jobs')
def jobs():
    return render_template('jobs.html', jobs=AI_Job_recommendation)

@app.route('/job-board')
def job_board():
    return render_template('job_board.html', jobs=AI_Job_recommendation)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('login.html')

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute("SELECT id, password_hash FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

            if user and check_password_hash(user[1], password):
                # Generate JWT token
                payload = {
                    'user_id': user[0],
                    'email': email,
                    'exp': datetime.now(timezone.utc) + timedelta(hours=24)
                }
                token = jwt.encode(payload, app.secret_key, algorithm='HS256')

                # Create response and set cookie
                resp = make_response(redirect(url_for('home')))
                resp.set_cookie('jwt_token', token, httponly=True, samesite='Lax')
                flash('Login successful!', 'success')
                return resp
            else:
                flash('Invalid email or password', 'error')
                return render_template('login.html')

        except Exception as e:
            flash(f'An error occurred: {e}', 'error')
            return render_template('login.html')
        finally:
            cur.close()
            conn.close()
        
    return render_template('login.html')


@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash('Email and password are required', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check if user already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            flash('Email already registered', 'error')
            return redirect(url_for('login'))

        # Hash password and insert new user
        password_hash = generate_password_hash(password)
        cur.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id", (email, password_hash))
        user_id = cur.fetchone()[0]
        conn.commit()

        # Generate JWT token
        payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.now(timezone.utc) + timedelta(hours=24)
        }
        token = jwt.encode(payload, app.secret_key, algorithm='HS256')

        # Create response and set cookie
        resp = make_response(redirect(url_for('home')))
        resp.set_cookie('jwt_token', token, httponly=True, samesite='Lax')
        flash('Registration successful!', 'success')
        return resp

    except Exception as e:
        conn.rollback()
        flash(f'An error occurred: {e}', 'error')
        return redirect(url_for('login'))
    finally:
        cur.close()
        conn.close()

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('home')))
    resp.set_cookie('jwt_token', '', expires=0)
    flash('You have been logged out.', 'success')
    return resp

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

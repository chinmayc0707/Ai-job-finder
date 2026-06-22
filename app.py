from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os

app = Flask(__name__)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = os.path.join(app.root_path, 'assets')
    return send_from_directory(assets_dir, filename)
app.secret_key = 'supersecretkey' # Required for flashing messages


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
        
        # For now, we'll just implement a simple check for demonstration
        if email and password:
            return redirect(url_for('home'))
        
    return render_template('login.html')


@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    password = request.form.get('password')
    # Simple check for demonstration
    if email and password:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

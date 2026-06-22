from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os

app = Flask(__name__)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = os.path.join(app.root_path, 'assets')
    return send_from_directory(assets_dir, filename)
app.secret_key = 'supersecretkey' # Required for flashing messages

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



@app.route('/services')
def services():
    return render_template('services.html')

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

# AI Job Portal

This is a Flask-based web application that serves as a job portal with a focus on AI-based resume matching and job recommendations.

## Features

- **Home Page**: A landing page introducing the platform.
- **Job Board / Jobs List**: Displays a list of available job postings including details like title, location, salary, and type (e.g., Full-time, Contract).
- **AI Resume Matching** (Concept): Designed to match candidates with the right jobs using AI.
- **About Page**: Information about the platform.
- **Login/Registration**: Simple user authentication flow.

## Tech Stack

- **Backend**: Python 3, Flask
- **Frontend**: HTML5, Custom CSS (using design tokens, not Bootstrap)
- **Deployment**: Gunicorn (for production)

## Application Structure

- `app.py`: The main Flask application file defining routes and serving pages.
- `templates/`: Contains all the HTML templates for the application (e.g., `index.html`, `jobs.html`, `login.html`).
- `static/`: Directory for static assets.
- `assets/`: Directory for images and other media assets served via a custom route.

## Setup

1. **Install dependencies:**
   Make sure you have Python 3 installed. Then, install the required packages using pip:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application locally:**
   Start the development server:
   ```bash
   python3 app.py
   ```
   The application will be available at `http://localhost:5000`.

3. **Run the application in production:**
   For a production environment, use a WSGI server like Gunicorn:
   ```bash
   gunicorn app:app
   ```

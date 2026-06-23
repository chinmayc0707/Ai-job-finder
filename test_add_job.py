"""Integration tests for the Add Job feature."""
import unittest
from app import app, generate_token


class TestAddJobFeature(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Generate a valid token for test user
        self.token = generate_token('test@example.com')

    def test_add_job_requires_login(self):
        """GET /add-job without auth should redirect to login."""
        response = self.app.get('/add-job')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

    def test_add_job_page_renders_for_logged_in_user(self):
        """GET /add-job with auth should return 200 and the form."""
        self.app.set_cookie('auth_token', self.token)
        response = self.app.get('/add-job')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Post a Job', html)
        self.assertIn('name="title"', html)
        self.assertIn('name="company"', html)
        self.assertIn('name="location"', html)
        self.assertIn('name="job_type"', html)
        self.assertIn('btn-submit', html)

    def test_add_job_validation_missing_fields(self):
        """POST /add-job with missing required fields should show error."""
        self.app.set_cookie('auth_token', self.token)
        response = self.app.post('/add-job', data={
            'title': '',
            'company': '',
            'location': '',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('required', html.lower())

    def test_add_job_success(self):
        """POST /add-job with valid data should create a job and redirect."""
        self.app.set_cookie('auth_token', self.token)
        response = self.app.post('/add-job', data={
            'title': 'Test Engineer',
            'company': 'TestCorp',
            'location': 'Remote',
            'salary': '$100k - $120k',
            'job_type': 'Full-time',
            'description': 'A test job listing.',
        })
        # Should redirect to /jobs on success
        self.assertEqual(response.status_code, 302)
        self.assertIn('/jobs', response.headers.get('Location', ''))

    def test_jobs_page_shows_db_job(self):
        """After adding a job, GET /jobs should display it."""
        # First add a job
        self.app.set_cookie('auth_token', self.token)
        self.app.post('/add-job', data={
            'title': 'Integration Test Role',
            'company': 'IntegrationCo',
            'location': 'Bangalore',
            'salary': '₹20L - ₹30L',
            'job_type': 'Contract',
            'description': 'Testing the jobs page.',
        })
        # Now check the jobs page
        response = self.app.get('/jobs')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Integration Test Role', html)
        self.assertIn('IntegrationCo', html)
        self.assertIn('Bangalore', html)

    def test_navbar_add_job_link_logged_in(self):
        """When logged in, the index page navbar dropdown should have Add Job link."""
        self.app.set_cookie('auth_token', self.token)
        response = self.app.get('/')
        html = response.data.decode('utf-8')
        self.assertIn('href="/add-job"', html)
        self.assertIn('Add Job', html)

    def test_navbar_no_add_job_link_logged_out(self):
        """When logged out, the index page should not have Add Job link."""
        response = self.app.get('/')
        html = response.data.decode('utf-8')
        self.assertNotIn('href="/add-job"', html)


if __name__ == '__main__':
    unittest.main()

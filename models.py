from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import os

DATABASE_URL = os.getenv('DATABASE_URL')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class Job(Base):
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    salary = Column(String(100), nullable=True)
    job_type = Column(String(50), nullable=False, default='Full-time')
    description = Column(Text, nullable=True)
    posted_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))

    def to_dict(self):
        """Convert Job to a dictionary for template rendering."""
        return {
            'id': self.id,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'salary': self.salary or 'Not specified',
            'type': self.job_type,
            'description': self.description or '',
            'posted_by': self.posted_by,
            'created_at': self.created_at,
        }

    def __repr__(self):
        return f'<Job {self.title} at {self.company}>'

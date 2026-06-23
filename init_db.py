"""Run this script once to create the users table in your Supabase PostgreSQL database."""
from dotenv import load_dotenv
load_dotenv()

from models import Base, engine

if __name__ == '__main__':
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Done! 'users' table created successfully.")

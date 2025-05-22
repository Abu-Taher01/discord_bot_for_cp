import sqlite3
import os
from datetime import datetime

# Database file path
DB_FILE = 'codeforces_bot.db'

def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database by creating tables if they don't exist."""
    print("Attempting to initialize database...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        discord_id INTEGER PRIMARY KEY,
        cf_handle TEXT NOT NULL,
        timezone TEXT DEFAULT 'UTC'
    )
    ''')

    # Create contests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        duration TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL,
        status TEXT NOT NULL,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        leaderboard_message_id INTEGER,
        channel_id INTEGER,
        FOREIGN KEY (created_by) REFERENCES users (discord_id)
    )
    ''')

    # Create contest_participants table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contest_participants (
        contest_id INTEGER,
        discord_id INTEGER,
        score INTEGER DEFAULT 0,
        PRIMARY KEY (contest_id, discord_id),
        FOREIGN KEY (contest_id) REFERENCES contests (id),
        FOREIGN KEY (discord_id) REFERENCES users (discord_id)
    )
    ''')

    # Create contest_problems table
    print("Attempting to create contest_problems table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contest_problems (
        contest_id INTEGER,
        problem_id TEXT NOT NULL,
        problem_name TEXT NOT NULL,
        problem_rating INTEGER,
        problem_tags TEXT,
        PRIMARY KEY (contest_id, problem_id),
        FOREIGN KEY (contest_id) REFERENCES contests (id)
    )
    ''')

    # Create daily_goals table with enhanced features
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_goals (
        discord_id INTEGER PRIMARY KEY,
        daily_goal INTEGER NOT NULL,
        weekly_goal INTEGER,
        monthly_goal INTEGER,
        solved_today INTEGER DEFAULT 0,
        solved_this_week INTEGER DEFAULT 0,
        solved_this_month INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        last_check TIMESTAMP,
        last_updated TIMESTAMP,
        reminder_time TEXT,
        FOREIGN KEY (discord_id) REFERENCES users(discord_id)
    )
    ''')

    # Create goal_categories table for tracking goals by difficulty
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS goal_categories (
        discord_id INTEGER,
        category_type TEXT NOT NULL,
        category_value TEXT NOT NULL,
        goal_count INTEGER NOT NULL,
        current_count INTEGER DEFAULT 0,
        last_updated TIMESTAMP,
        PRIMARY KEY (discord_id, category_type, category_value),
        FOREIGN KEY (discord_id) REFERENCES users(discord_id)
    )
    ''')

    # Create goal_history table for tracking goal completion history
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS goal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id INTEGER,
        date DATE NOT NULL,
        goal_type TEXT NOT NULL,
        target INTEGER NOT NULL,
        achieved INTEGER NOT NULL,
        streak INTEGER NOT NULL,
        FOREIGN KEY (discord_id) REFERENCES users(discord_id)
    )
    ''')

    # Create streak_rewards table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS streak_rewards (
        discord_id INTEGER,
        streak_length INTEGER NOT NULL,
        reward_type TEXT NOT NULL,
        reward_value TEXT NOT NULL,
        claimed BOOLEAN DEFAULT FALSE,
        claimed_at TIMESTAMP,
        PRIMARY KEY (discord_id, streak_length),
        FOREIGN KEY (discord_id) REFERENCES users(discord_id)
    )
    ''')

    # Create contest_submissions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contest_submissions (
        contest_id INTEGER,
        discord_id INTEGER,
        problem_id TEXT NOT NULL,
        submission_id INTEGER NOT NULL,
        submission_time TIMESTAMP NOT NULL,
        verdict TEXT NOT NULL,
        PRIMARY KEY (contest_id, discord_id, problem_id, submission_id),
        FOREIGN KEY (contest_id) REFERENCES contests (id),
        FOREIGN KEY (discord_id) REFERENCES users (discord_id)
    )
    ''')

    conn.commit()
    conn.close()

# Initialize the database
init_db() 
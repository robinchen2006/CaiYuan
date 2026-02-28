from flask import g
import sqlite3
from werkzeug.security import generate_password_hash
import logging

def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect('notes.db')
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    """Initialize database tables"""
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        # User teams table - for grouping users who share notes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table with role, status, and team
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'pending',
                team_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES user_teams (id)
            )
        ''')
        
        # Note groups table - now shared within user teams
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                team_id INTEGER,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES user_teams (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT DEFAULT '',
                date TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                team_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (team_id) REFERENCES user_teams (id)
            )
        ''')
        
        # Images table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                note_id INTEGER,
                date TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                team_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES notes (id),
                FOREIGN KEY (group_id) REFERENCES groups (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (team_id) REFERENCES user_teams (id)
            )
        ''')
        
        # Migration: Add new columns if they don't exist
        migrations = [
            ('users', 'role', "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"),
            ('users', 'status', "ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'approved'"),
            ('users', 'team_id', "ALTER TABLE users ADD COLUMN team_id INTEGER REFERENCES user_teams(id)"),
            ('groups', 'team_id', "ALTER TABLE groups ADD COLUMN team_id INTEGER REFERENCES user_teams(id)"),
            ('notes', 'team_id', "ALTER TABLE notes ADD COLUMN team_id INTEGER REFERENCES user_teams(id)"),
            ('images', 'team_id', "ALTER TABLE images ADD COLUMN team_id INTEGER REFERENCES user_teams(id)"),
            ('images', 'note_id', "ALTER TABLE images ADD COLUMN note_id INTEGER REFERENCES notes(id)"),
        ]
        
        for table, column, sql in migrations:
            try:
                cursor.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        # Create default admin user if not exists
        cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            password_hash = generate_password_hash('admin123')
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, status) 
                VALUES (?, ?, 'admin', 'approved')
            ''', ('admin', password_hash))
        else:
            # Ensure admin has correct role and status
            cursor.execute('''
                UPDATE users SET role = 'admin', status = 'approved' 
                WHERE username = 'admin'
            ''')
        
        conn.commit()
        app.logger.info('Database initialized successfully')

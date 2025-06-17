from flask import Flask, jsonify, request, render_template, redirect, url_for, session, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
import os, requests
import sqlite3
from contextlib import closing

app = Flask(__name__)
app.secret_key = 'supersecretkey_here'  # Required for session management

# SQLite database setup
DATABASE = 'task_manager.db'

def init_db():
    with closing(sqlite3.connect(DATABASE)) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

# Create schema.sql file (or initialize tables directly)
with open('schema.sql', 'w') as f:
    f.write("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'To Do',
        assignee TEXT
    );
    
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        comment TEXT NOT NULL,
        author TEXT NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks (id)
    );
    """)

# Initialize the database
init_db()

TEMPLATE_URLS = {
    'index': 'https://mysecurecorpfiles.blob.core.windows.net/static/index.html',
    'login': 'https://mysecurecorpfiles.blob.core.windows.net/static/login.html',
    'register': 'https://mysecurecorpfiles.blob.core.windows.net/static/register.html',
}

def get_template(template_name):
    url = TEMPLATE_URLS.get(template_name)
    if url:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
    return "<h1>Template not found</h1>"

# Routes
@app.route('/')
def index():
    if 'username' in session:
        template = get_template('index')
        return render_template_string(template, username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    template = get_template('login')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('index'))
        return "Invalid username or password"
    return render_template_string(template)

@app.route('/register', methods=['GET', 'POST'])
def register():
    template = get_template('register')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                       (username, hashed_password))
            db.commit()
            db.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            db.close()
            return "Username already exists"
    return render_template_string(template)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/tasks', methods=['GET'])
def get_tasks():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    tasks = db.execute('SELECT id, title, description, status, assignee FROM tasks').fetchall()
    db.close()
    
    return jsonify([dict(task) for task in tasks])

@app.route('/tasks', methods=['POST'])
def create_task():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    db = get_db()
    db.execute('INSERT INTO tasks (title, description, status, assignee) VALUES (?, ?, ?, ?)',
               (data['title'], data['description'], data.get('status', 'To Do'), data['assignee']))
    db.commit()
    db.close()
    
    return jsonify({"message": "Task created!"})

@app.route('/tasks/<int:task_id>/comments', methods=['POST'])
def add_comment(task_id):
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    db = get_db()
    db.execute('INSERT INTO comments (task_id, comment, author) VALUES (?, ?, ?)',
               (task_id, data['comment'], session['username']))
    db.commit()
    db.close()
    
    return jsonify({"message": "Comment added!"})

@app.route('/tasks/<int:task_id>/comments', methods=['GET'])
def get_comments(task_id):
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    comments = db.execute('SELECT id, task_id, comment, author FROM comments WHERE task_id = ?', 
                         (task_id,)).fetchall()
    db.close()
    
    return jsonify([dict(comment) for comment in comments])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
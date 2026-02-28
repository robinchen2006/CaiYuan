from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def get_db():
    """Get database connection"""
    conn = sqlite3.connect('notes.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables"""
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
    conn.close()


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_user_team_id():
    """Get current user's team_id"""
    return session.get('team_id')


# ============ Auth Routes ============

@app.route('/')
def index():
    """Redirect to main page or login"""
    if 'user_id' in session:
        return redirect(url_for('main'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and password and check_password_hash(user['password_hash'], password):
            # Check if user is approved
            if user['status'] == 'pending':
                flash('您的账号正在等待管理员审核', 'error')
                return render_template('login.html')
            elif user['status'] == 'rejected':
                flash('您的账号已被拒绝', 'error')
                return render_template('login.html')
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['team_id'] = user['team_id']
            return redirect(url_for('main'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not password:
            flash('请填写所有字段', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('两次密码不一致', 'error')
            return render_template('register.html')
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            password_hash = generate_password_hash(password)
            # New users start with 'pending' status
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, status) 
                VALUES (?, ?, 'user', 'pending')
            ''', (username, password_hash))
            conn.commit()
            flash('注册成功，请等待管理员审核后登录', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('用户名已存在', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')


@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))


# ============ Main Routes ============

@app.route('/main')
@login_required
def main():
    """Main page"""
    return render_template('main.html', 
                          username=session.get('username'),
                          role=session.get('role'))


# ============ Password Change API ============

@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({'error': '请填写所有字段'}), 400
    
    if len(new_password) < 4:
        return jsonify({'error': '新密码至少需要4个字符'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not check_password_hash(user['password_hash'], old_password):
        conn.close()
        return jsonify({'error': '原密码错误'}), 400
    
    new_hash = generate_password_hash(new_password)
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                  (new_hash, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({'message': '密码修改成功'})


# ============ Admin User Management APIs ============

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_all_users():
    """Get all users (admin only)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.role, u.status, u.team_id, u.created_at,
               t.name as team_name
        FROM users u
        LEFT JOIN user_teams t ON u.team_id = t.id
        ORDER BY u.created_at DESC
    ''')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(users)


@app.route('/api/admin/users/pending', methods=['GET'])
@admin_required
def get_pending_users():
    """Get pending users (admin only)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, created_at 
        FROM users 
        WHERE status = 'pending'
        ORDER BY created_at ASC
    ''')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(users)


@app.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_user(user_id):
    """Approve a pending user (admin only)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET status = 'approved' 
        WHERE id = ? AND status = 'pending'
    ''', (user_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    if affected:
        return jsonify({'message': '用户已通过审核'})
    else:
        return jsonify({'error': '用户不存在或已审核'}), 400


@app.route('/api/admin/users/<int:user_id>/reject', methods=['POST'])
@admin_required
def reject_user(user_id):
    """Reject a pending user (admin only)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET status = 'rejected' 
        WHERE id = ? AND status = 'pending'
    ''', (user_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    
    if affected:
        return jsonify({'message': '用户已被拒绝'})
    else:
        return jsonify({'error': '用户不存在或已审核'}), 400


@app.route('/api/admin/users/<int:user_id>/team', methods=['PUT'])
@admin_required
def assign_user_team(user_id):
    """Assign user to a team (admin only) and migrate their existing notes/groups"""
    data = request.get_json()
    team_id = data.get('team_id')  # Can be null to remove from team
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify team exists if team_id provided
    if team_id:
        cursor.execute('SELECT id FROM user_teams WHERE id = ?', (team_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': '用户组不存在'}), 400
    
    # Update user's team
    cursor.execute('UPDATE users SET team_id = ? WHERE id = ?', (team_id, user_id))
    
    # Migrate user's existing groups to the new team
    cursor.execute('UPDATE groups SET team_id = ? WHERE user_id = ?', (team_id, user_id))
    
    # Migrate user's existing notes to the new team
    cursor.execute('UPDATE notes SET team_id = ? WHERE user_id = ?', (team_id, user_id))
    
    # Migrate user's existing images to the new team
    cursor.execute('UPDATE images SET team_id = ? WHERE user_id = ?', (team_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': '用户组分配成功，已迁移用户的历史笔记和品类'})


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)"""
    if user_id == session['user_id']:
        return jsonify({'error': '不能删除自己'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if user is admin
    cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    if user and user['role'] == 'admin':
        conn.close()
        return jsonify({'error': '不能删除管理员账号'}), 400
    
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': '用户已删除'})


# ============ User Team Management APIs ============

@app.route('/api/admin/teams', methods=['GET'])
@admin_required
def get_user_teams():
    """Get all user teams (admin only)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, COUNT(u.id) as member_count
        FROM user_teams t
        LEFT JOIN users u ON u.team_id = t.id
        GROUP BY t.id
        ORDER BY t.created_at DESC
    ''')
    teams = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(teams)


@app.route('/api/admin/teams', methods=['POST'])
@admin_required
def create_user_team():
    """Create a user team (admin only)"""
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'error': '用户组名称不能为空'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO user_teams (name) VALUES (?)', (name,))
    conn.commit()
    team_id = cursor.lastrowid
    conn.close()
    
    return jsonify({'id': team_id, 'name': name, 'message': '用户组创建成功'})


@app.route('/api/admin/teams/<int:team_id>', methods=['PUT'])
@admin_required
def update_user_team(team_id):
    """Update user team name (admin only)"""
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'error': '用户组名称不能为空'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE user_teams SET name = ? WHERE id = ?', (name, team_id))
    conn.commit()
    conn.close()
    
    return jsonify({'message': '用户组更新成功'})


@app.route('/api/admin/teams/<int:team_id>', methods=['DELETE'])
@admin_required
def delete_user_team(team_id):
    """Delete a user team (admin only)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Remove team association from users
    cursor.execute('UPDATE users SET team_id = NULL WHERE team_id = ?', (team_id,))
    
    # Delete the team
    cursor.execute('DELETE FROM user_teams WHERE id = ?', (team_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': '用户组已删除'})


# ============ Note Group API Routes ============

@app.route('/api/groups', methods=['GET'])
@login_required
def get_groups():
    """Get all groups for current user's team"""
    conn = get_db()
    cursor = conn.cursor()
    
    team_id = get_user_team_id()
    
    if team_id:
        # Get groups shared within team
        cursor.execute('''
            SELECT * FROM groups 
            WHERE team_id = ? 
            ORDER BY created_at DESC
        ''', (team_id,))
    else:
        # User not in a team, get only their own groups
        cursor.execute('''
            SELECT * FROM groups 
            WHERE user_id = ? AND team_id IS NULL
            ORDER BY created_at DESC
        ''', (session['user_id'],))
    
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(groups)


@app.route('/api/groups', methods=['POST'])
@login_required
def create_group():
    """Create a new group"""
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'error': '品类名称不能为空'}), 400
    
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if group name already exists
    if team_id:
        cursor.execute('SELECT id FROM groups WHERE name = ? AND team_id = ?', (name, team_id))
    else:
        cursor.execute('SELECT id FROM groups WHERE name = ? AND user_id = ? AND team_id IS NULL', (name, session['user_id']))
        
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': '该品类名称已存在，请使用其他名称'}), 400
        
    cursor.execute('''
        INSERT INTO groups (name, user_id, team_id) 
        VALUES (?, ?, ?)
    ''', (name, session['user_id'], team_id))
    conn.commit()
    group_id = cursor.lastrowid
    conn.close()
    
    return jsonify({'id': group_id, 'name': name, 'message': '品类创建成功'})


@app.route('/api/groups/<int:group_id>', methods=['PUT'])
@login_required
def update_group(group_id):
    """Update group name"""
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'error': '品类名称不能为空'}), 400
    
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    if team_id:
        cursor.execute('''
            UPDATE groups SET name = ? 
            WHERE id = ? AND team_id = ?
        ''', (name, group_id, team_id))
    else:
        cursor.execute('''
            UPDATE groups SET name = ? 
            WHERE id = ? AND user_id = ? AND team_id IS NULL
        ''', (name, group_id, session['user_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': '品类更新成功'})


@app.route('/api/groups/<int:group_id>', methods=['DELETE'])
@login_required
def delete_group(group_id):
    """Delete a group and all its notes/images"""
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get all images in this group to delete files
    if team_id:
        cursor.execute('''
            SELECT filename FROM images 
            WHERE group_id = ? AND team_id = ?
        ''', (group_id, team_id))
    else:
        cursor.execute('''
            SELECT filename FROM images 
            WHERE group_id = ? AND user_id = ? AND team_id IS NULL
        ''', (group_id, session['user_id']))
    
    images = cursor.fetchall()
    
    # Delete image files
    for img in images:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    # Delete records from database
    if team_id:
        cursor.execute('DELETE FROM images WHERE group_id = ? AND team_id = ?',
                      (group_id, team_id))
        cursor.execute('DELETE FROM notes WHERE group_id = ? AND team_id = ?',
                      (group_id, team_id))
        cursor.execute('DELETE FROM groups WHERE id = ? AND team_id = ?',
                      (group_id, team_id))
    else:
        cursor.execute('DELETE FROM images WHERE group_id = ? AND user_id = ? AND team_id IS NULL',
                      (group_id, session['user_id']))
        cursor.execute('DELETE FROM notes WHERE group_id = ? AND user_id = ? AND team_id IS NULL',
                      (group_id, session['user_id']))
        cursor.execute('DELETE FROM groups WHERE id = ? AND user_id = ? AND team_id IS NULL',
                      (group_id, session['user_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': '品类删除成功'})


# ============ Note API Routes ============

@app.route('/api/notes', methods=['GET'])
@login_required
def get_notes():
    """Get notes with their images, optionally filtered by group"""
    group_id = request.args.get('group_id')
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    if team_id:
        if group_id:
            cursor.execute('''
                SELECT n.*, g.name as group_name, u.username as author
                FROM notes n 
                JOIN groups g ON n.group_id = g.id 
                LEFT JOIN users u ON n.user_id = u.id
                WHERE n.group_id = ? AND n.team_id = ?
                ORDER BY n.date DESC, n.created_at DESC
            ''', (group_id, team_id))
        else:
            cursor.execute('''
                SELECT n.*, g.name as group_name, u.username as author
                FROM notes n 
                JOIN groups g ON n.group_id = g.id 
                LEFT JOIN users u ON n.user_id = u.id
                WHERE n.team_id = ?
                ORDER BY n.date DESC, n.created_at DESC
            ''', (team_id,))
    else:
        if group_id:
            cursor.execute('''
                SELECT n.*, g.name as group_name, u.username as author
                FROM notes n 
                JOIN groups g ON n.group_id = g.id 
                LEFT JOIN users u ON n.user_id = u.id
                WHERE n.group_id = ? AND n.user_id = ? AND n.team_id IS NULL
                ORDER BY n.date DESC, n.created_at DESC
            ''', (group_id, session['user_id']))
        else:
            cursor.execute('''
                SELECT n.*, g.name as group_name, u.username as author
                FROM notes n 
                JOIN groups g ON n.group_id = g.id 
                LEFT JOIN users u ON n.user_id = u.id
                WHERE n.user_id = ? AND n.team_id IS NULL
                ORDER BY n.date DESC, n.created_at DESC
            ''', (session['user_id'],))
    
    notes = []
    for row in cursor.fetchall():
        note = dict(row)
        # Get images for this note
        cursor.execute('''
            SELECT id, filename, original_filename 
            FROM images 
            WHERE note_id = ?
            ORDER BY created_at ASC
        ''', (note['id'],))
        note['images'] = [dict(img) for img in cursor.fetchall()]
        notes.append(note)
    
    conn.close()
    
    return jsonify(notes)


@app.route('/api/notes', methods=['POST'])
@login_required
def create_note():
    """Create a new note with optional images"""
    content = request.form.get('content', '').strip()
    date = request.form.get('date')
    group_id = request.form.get('group_id')
    
    if not date or not group_id:
        return jsonify({'error': '请填写日期和品类'}), 400
    
    files = request.files.getlist('images')
    has_images = any(f.filename for f in files)
    
    if not content and not has_images:
        return jsonify({'error': '请输入笔记内容或上传图片'}), 400
    
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO notes (content, date, group_id, user_id, team_id) 
            VALUES (?, ?, ?, ?, ?)
        ''', (content, date, group_id, session['user_id'], team_id))
        note_id = cursor.lastrowid
        
        saved_images = []
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                original_filename = secure_filename(file.filename) or 'image'
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                filename = f"{session['user_id']}_{timestamp}_{original_filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                cursor.execute('''
                    INSERT INTO images (filename, original_filename, note_id, date, group_id, user_id, team_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (filename, original_filename, note_id, date, group_id, session['user_id'], team_id))
                saved_images.append({
                    'id': cursor.lastrowid,
                    'filename': filename,
                    'original_filename': original_filename
                })
        
        conn.commit()
        
        return jsonify({
            'id': note_id,
            'images': saved_images,
            'message': '笔记保存成功'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/notes/<int:note_id>', methods=['PUT'])
@login_required
def update_note(note_id):
    """Update a note"""
    content = request.form.get('content', '').strip()
    date = request.form.get('date')
    group_id = request.form.get('group_id')
    keep_images = request.form.get('keep_images', '[]')
    
    if not date or not group_id:
        return jsonify({'error': '请填写日期和品类'}), 400
    
    try:
        keep_image_ids = json.loads(keep_images)
    except:
        keep_image_ids = []
    
    files = request.files.getlist('images')
    has_new_images = any(f.filename for f in files)
    
    if not content and not keep_image_ids and not has_new_images:
        return jsonify({'error': '请输入笔记内容或保留/上传图片'}), 400
    
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Verify note belongs to user or team
        if team_id:
            cursor.execute('SELECT id FROM notes WHERE id = ? AND team_id = ?', (note_id, team_id))
        else:
            cursor.execute('SELECT id FROM notes WHERE id = ? AND user_id = ? AND team_id IS NULL', 
                          (note_id, session['user_id']))
        
        if not cursor.fetchone():
            return jsonify({'error': '笔记不存在或无权限'}), 403
        
        cursor.execute('''
            UPDATE notes 
            SET content = ?, date = ?, group_id = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (content, date, group_id, note_id))
        
        # Delete images not in keep_images
        if keep_image_ids:
            placeholders = ','.join('?' * len(keep_image_ids))
            cursor.execute(f'''
                SELECT filename FROM images 
                WHERE note_id = ? AND id NOT IN ({placeholders})
            ''', [note_id] + keep_image_ids)
        else:
            cursor.execute('SELECT filename FROM images WHERE note_id = ?', (note_id,))
        
        images_to_delete = cursor.fetchall()
        for img in images_to_delete:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
            if os.path.exists(filepath):
                os.remove(filepath)
        
        if keep_image_ids:
            placeholders = ','.join('?' * len(keep_image_ids))
            cursor.execute(f'DELETE FROM images WHERE note_id = ? AND id NOT IN ({placeholders})',
                          [note_id] + keep_image_ids)
        else:
            cursor.execute('DELETE FROM images WHERE note_id = ?', (note_id,))
        
        # Save new images
        saved_images = []
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                original_filename = secure_filename(file.filename) or 'image'
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                filename = f"{session['user_id']}_{timestamp}_{original_filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                cursor.execute('''
                    INSERT INTO images (filename, original_filename, note_id, date, group_id, user_id, team_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (filename, original_filename, note_id, date, group_id, session['user_id'], team_id))
                saved_images.append({'id': cursor.lastrowid, 'filename': filename})
        
        conn.commit()
        
        return jsonify({'message': '笔记更新成功', 'new_images': saved_images})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
@login_required
def delete_note(note_id):
    """Delete a note and its images"""
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify permission
    if team_id:
        cursor.execute('SELECT id FROM notes WHERE id = ? AND team_id = ?', (note_id, team_id))
    else:
        cursor.execute('SELECT id FROM notes WHERE id = ? AND user_id = ? AND team_id IS NULL',
                      (note_id, session['user_id']))
    
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '笔记不存在或无权限'}), 403
    
    # Get images to delete files
    cursor.execute('SELECT filename FROM images WHERE note_id = ?', (note_id,))
    images = cursor.fetchall()
    
    for img in images:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    cursor.execute('DELETE FROM images WHERE note_id = ?', (note_id,))
    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': '笔记删除成功'})


@app.route('/api/notes/<int:note_id>/images/<int:image_id>', methods=['DELETE'])
@login_required
def delete_note_image(note_id, image_id):
    """Delete a single image from a note"""
    team_id = get_user_team_id()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify permission
    if team_id:
        cursor.execute('SELECT id FROM notes WHERE id = ? AND team_id = ?', (note_id, team_id))
    else:
        cursor.execute('SELECT id FROM notes WHERE id = ? AND user_id = ? AND team_id IS NULL',
                      (note_id, session['user_id']))
    
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '笔记不存在或无权限'}), 403
    
    cursor.execute('SELECT filename FROM images WHERE id = ? AND note_id = ?', (image_id, note_id))
    image = cursor.fetchone()
    
    if image:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], image['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        
        cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
        conn.commit()
    
    conn.close()
    
    return jsonify({'message': '图片删除成功'})


# ============ User Info API ============

@app.route('/api/user/info', methods=['GET'])
@login_required
def get_user_info():
    """Get current user info"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.role, u.status, u.team_id, t.name as team_name
        FROM users u
        LEFT JOIN user_teams t ON u.team_id = t.id
        WHERE u.id = ?
    ''', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return jsonify(dict(user))
    return jsonify({'error': '用户不存在'}), 404


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)

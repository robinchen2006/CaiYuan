from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from utils import login_required
import sqlite3

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    """Redirect to main page or login"""
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        
        if user and password and check_password_hash(user['password_hash'], password):
            # Check if user is approved
            if user['status'] == 'pending':
                current_app.logger.warning(f'Login attempt by pending user: {username}')
                flash('您的账号正在等待管理员审核', 'error')
                return render_template('login.html')
            elif user['status'] == 'rejected':
                current_app.logger.warning(f'Login attempt by rejected user: {username}')
                flash('您的账号已被拒绝', 'error')
                return render_template('login.html')
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['team_id'] = user['team_id']
            current_app.logger.info(f'User logged in successfully: {username}')
            return redirect(url_for('main.index'))
        else:
            current_app.logger.warning(f'Failed login attempt for username: {username}')
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
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
            current_app.logger.info(f'New user registration: {username}')
            flash('注册成功，请等待管理员审核后登录', 'success')
            return redirect(url_for('auth.login'))
        except sqlite3.IntegrityError:
            current_app.logger.warning(f'Registration failed - username exists: {username}')
            flash('用户名已存在', 'error')
        
    return render_template('register.html')

@auth_bp.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/change-password', methods=['POST'])
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
        return jsonify({'error': '原密码错误'}), 400
    
    new_hash = generate_password_hash(new_password)
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                  (new_hash, session['user_id']))
    conn.commit()
    
    current_app.logger.info(f'User {session["user_id"]} changed password')
    return jsonify({'message': '密码修改成功'})

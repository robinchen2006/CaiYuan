from flask import Blueprint, jsonify, request, session, current_app
from database import get_db
from utils import login_required, get_user_team_id, allowed_file
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json

notes_bp = Blueprint('notes', __name__)

# ============ Note Group API Routes ============

@notes_bp.route('/groups', methods=['GET'])
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
    return jsonify(groups)


@notes_bp.route('/groups', methods=['POST'])
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
        return jsonify({'error': '该品类名称已存在，请使用其他名称'}), 400
        
    cursor.execute('''
        INSERT INTO groups (name, user_id, team_id) 
        VALUES (?, ?, ?)
    ''', (name, session['user_id'], team_id))
    conn.commit()
    group_id = cursor.lastrowid
    
    current_app.logger.info(f'User {session["user_id"]} created group: {name} (id: {group_id}, team: {team_id})')
    return jsonify({'id': group_id, 'name': name, 'message': '品类创建成功'})


@notes_bp.route('/groups/<int:group_id>', methods=['PUT'])
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
    
    return jsonify({'message': '品类更新成功'})


@notes_bp.route('/groups/<int:group_id>', methods=['DELETE'])
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
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], img['filename'])
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
    
    current_app.logger.info(f'User {session["user_id"]} deleted group: {group_id} (team: {team_id})')
    return jsonify({'message': '品类删除成功'})


# ============ Note API Routes ============

@notes_bp.route('/notes', methods=['GET'])
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
    
    return jsonify(notes)


@notes_bp.route('/notes', methods=['POST'])
@login_required
def create_note():
    """Create a new note with optional images"""
    content = request.form.get('content', '').strip()
    date = request.form.get('date')
    group_id = request.form.get('group_id')
    
    if not date or not group_id:
        return jsonify({'error': '请填写日期和品类'}), 400
    
    files = request.files.getlist('images')
    uploaded_chunks_json = request.form.get('uploaded_chunks', '[]')
    try:
        uploaded_chunks = json.loads(uploaded_chunks_json)
    except Exception:
        uploaded_chunks = []
        
    has_images = any(f.filename for f in files) or len(uploaded_chunks) > 0
    
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
        
        # Process pre-uploaded chunked files
        for chunk_file in uploaded_chunks:
            if chunk_file and 'filename' in chunk_file:
                # filename is relative path like "username/123_abc.jpg"
                filename = chunk_file['filename']
                original_filename = chunk_file.get('original_filename', 'image')
                
                cursor.execute('''
                    INSERT INTO images (filename, original_filename, note_id, date, group_id, user_id, team_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (filename, original_filename, note_id, date, group_id, session['user_id'], team_id))
                
                saved_images.append({
                    'id': cursor.lastrowid,
                    'filename': filename,
                    'original_filename': original_filename
                })
        
        # Process standard file uploads
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                original_filename = secure_filename(file.filename) or 'image'
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                
                # Create user directory if not exists
                # Sanitize username for directory name security
                username = secure_filename(session.get('username', 'shared'))
                if not username:
                    username = 'user_' + str(session.get('user_id', 'unknown'))
                
                user_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], username)
                os.makedirs(user_folder, exist_ok=True)
                
                # Filename without path
                name = f"{session['user_id']}_{timestamp}_{original_filename}"
                
                # Save file
                filepath = os.path.join(user_folder, name)
                file.save(filepath)
                
                # Update filename to include user path for access
                # Use forward slash for web URL compatibility
                filename = f"{username}/{name}"
                
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
        
        current_app.logger.info(f'User {session["user_id"]} created note: {note_id} in group {group_id}')
        return jsonify({
            'id': note_id,
            'images': saved_images,
            'message': '笔记保存成功'
        })
    except Exception as e:
        current_app.logger.error(f'Error creating note for user {session["user_id"]}: {str(e)}', exc_info=True)
        conn.rollback()
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes/<int:note_id>', methods=['PUT'])
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
    except Exception:
        keep_image_ids = []
    
    files = request.files.getlist('images')
    uploaded_chunks_json = request.form.get('uploaded_chunks', '[]')
    try:
        uploaded_chunks = json.loads(uploaded_chunks_json)
    except Exception:
        uploaded_chunks = []
        
    has_new_images = any(f.filename for f in files) or len(uploaded_chunks) > 0
    
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
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], img['filename'])
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
        
        # Process pre-uploaded chunked files
        for chunk_file in uploaded_chunks:
            if chunk_file and 'filename' in chunk_file:
                filename = chunk_file['filename']
                original_filename = chunk_file.get('original_filename', 'image')
                
                cursor.execute('''
                    INSERT INTO images (filename, original_filename, note_id, date, group_id, user_id, team_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (filename, original_filename, note_id, date, group_id, session['user_id'], team_id))
                saved_images.append({'id': cursor.lastrowid, 'filename': filename})
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                original_filename = secure_filename(file.filename) or 'image'
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                
                # Create user directory if not exists
                # Sanitize username for directory name security
                current_username = secure_filename(session.get('username', 'shared'))
                if not current_username:
                    current_username = 'user_' + str(session.get('user_id', 'unknown'))
                
                user_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], current_username)
                os.makedirs(user_folder, exist_ok=True)
                
                # Filename without path
                name = f"{session['user_id']}_{timestamp}_{original_filename}"
                
                # Save file
                filepath = os.path.join(user_folder, name)
                file.save(filepath)
                
                # Filename with relative path
                filename = f"{current_username}/{name}"
                
                cursor.execute('''
                    INSERT INTO images (filename, original_filename, note_id, date, group_id, user_id, team_id) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (filename, original_filename, note_id, date, group_id, session['user_id'], team_id))
                saved_images.append({'id': cursor.lastrowid, 'filename': filename})
        
        conn.commit()
        
        current_app.logger.info(f'User {session["user_id"]} updated note: {note_id}')
        return jsonify({'message': '笔记更新成功', 'new_images': saved_images})
    except Exception as e:
        current_app.logger.error(f'Error updating note {note_id} for user {session["user_id"]}: {str(e)}', exc_info=True)
        conn.rollback()
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/notes/<int:note_id>', methods=['DELETE'])
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
        current_app.logger.warning(f'User {session.get("user_id")} attempted to delete non-existent or unauthorized note: {note_id}')
        return jsonify({'error': '笔记不存在或无权限'}), 403
    
    # Get images to delete files
    cursor.execute('SELECT filename FROM images WHERE note_id = ?', (note_id,))
    images = cursor.fetchall()
    
    for img in images:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], img['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    
    cursor.execute('DELETE FROM images WHERE note_id = ?', (note_id,))
    cursor.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    
    current_app.logger.info(f'User {session.get("user_id")} deleted note: {note_id}')
    return jsonify({'message': '笔记删除成功'})


@notes_bp.route('/notes/<int:note_id>/images/<int:image_id>', methods=['DELETE'])
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
        return jsonify({'error': '笔记不存在或无权限'}), 403
    
    cursor.execute('SELECT filename FROM images WHERE id = ? AND note_id = ?', (image_id, note_id))
    image = cursor.fetchone()
    
    if image:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], image['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        
        cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
        conn.commit()
        current_app.logger.info(f'User {session.get("user_id")} deleted image {image_id} from note {note_id}')
    
    conn.close()
    return jsonify({'message': '图片删除成功'})


# ============ User Info API ============

@notes_bp.route('/user/info', methods=['GET'])
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

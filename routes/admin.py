from flask import Blueprint, jsonify, request, session, current_app
from database import get_db
from utils import admin_required, login_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
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
    return jsonify(users)

@admin_bp.route('/users/pending', methods=['GET'])
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
    return jsonify(users)

@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
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
    
    if affected:
        current_app.logger.info(f'Admin approved user id: {user_id}')
        return jsonify({'message': '用户已通过审核'})
    else:
        current_app.logger.warning(f'Admin failed to approve user id: {user_id} (not found or not pending)')
        return jsonify({'error': '用户不存在或已审核'}), 400

@admin_bp.route('/users/<int:user_id>/reject', methods=['POST'])
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
    
    if affected:
        current_app.logger.info(f'Admin rejected user id: {user_id}')
        return jsonify({'message': '用户已被拒绝'})
    else:
        current_app.logger.warning(f'Admin failed to reject user id: {user_id} (not found or not pending)')
        return jsonify({'error': '用户不存在或已审核'}), 400

@admin_bp.route('/users/<int:user_id>/team', methods=['PUT'])
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
    
    current_app.logger.info(f'Admin assigned user {user_id} to team {team_id if team_id else "None"}')
    return jsonify({'message': '用户组分配成功，已迁移用户的历史笔记和品类'})

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)"""
    if user_id == session['user_id']:
        current_app.logger.warning(f'Admin tried to delete themselves: {user_id}')
        return jsonify({'error': '不能删除自己'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if user is admin
    cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    if user and user['role'] == 'admin':
        current_app.logger.warning(f'Admin tried to delete another admin: {user_id}')
        return jsonify({'error': '不能删除管理员账号'}), 400
    
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    
    current_app.logger.info(f'Admin deleted user: {user_id}')
    return jsonify({'message': '用户已删除'})

@admin_bp.route('/teams', methods=['GET'])
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
    return jsonify(teams)

@admin_bp.route('/teams', methods=['POST'])
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
    
    return jsonify({'id': team_id, 'name': name, 'message': '用户组创建成功'})

@admin_bp.route('/teams/<int:team_id>', methods=['PUT'])
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
    
    return jsonify({'message': '用户组更新成功'})

@admin_bp.route('/teams/<int:team_id>', methods=['DELETE'])
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
    
    return jsonify({'message': '用户组已删除'})


@admin_bp.route('/projects', methods=['GET'])
@admin_required
def get_projects():
    """Get all projects (admin only)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.name, p.created_at,
               COUNT(DISTINCT g.id) as group_count,
               COUNT(DISTINCT n.id) as note_count
        FROM projects p
        LEFT JOIN groups g ON g.project_id = p.id
        LEFT JOIN notes n ON n.project_id = p.id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    ''')
    projects = [dict(row) for row in cursor.fetchall()]
    return jsonify(projects)


@admin_bp.route('/projects', methods=['POST'])
@admin_required
def create_project():
    """Create a new project (admin only)"""
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': '项目名称不能为空'}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM projects WHERE name = ?', (name,))
    if cursor.fetchone():
        return jsonify({'error': '项目名称已存在'}), 400

    cursor.execute('INSERT INTO projects (name) VALUES (?)', (name,))
    conn.commit()
    project_id = cursor.lastrowid

    return jsonify({'id': project_id, 'name': name, 'message': '项目创建成功'})


@admin_bp.route('/projects/<int:project_id>', methods=['PUT'])
@admin_required
def update_project(project_id):
    """Update project name (admin only)"""
    data = request.get_json()
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': '项目名称不能为空'}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM projects WHERE id = ?', (project_id,))
    if not cursor.fetchone():
        return jsonify({'error': '项目不存在'}), 404

    cursor.execute('SELECT id FROM projects WHERE name = ? AND id != ?', (name, project_id))
    if cursor.fetchone():
        return jsonify({'error': '项目名称已存在'}), 400

    cursor.execute('UPDATE projects SET name = ? WHERE id = ?', (name, project_id))
    conn.commit()
    return jsonify({'message': '项目更新成功'})


@admin_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@admin_required
def delete_project(project_id):
    """Delete project (admin only)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id, name FROM projects WHERE id = ?', (project_id,))
    project = cursor.fetchone()
    if not project:
        return jsonify({'error': '项目不存在'}), 404

    cursor.execute('SELECT COUNT(*) as count FROM projects')
    total_projects = cursor.fetchone()['count']
    if total_projects <= 1:
        return jsonify({'error': '至少保留一个项目'}), 400

    cursor.execute('SELECT COUNT(*) as count FROM groups WHERE project_id = ?', (project_id,))
    group_count = cursor.fetchone()['count']
    cursor.execute('SELECT COUNT(*) as count FROM notes WHERE project_id = ?', (project_id,))
    note_count = cursor.fetchone()['count']
    if group_count > 0 or note_count > 0:
        return jsonify({'error': '该项目下仍有品类或笔记，无法删除'}), 400

    cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    cursor.execute('''
        UPDATE users
        SET current_project_id = (SELECT id FROM projects ORDER BY id ASC LIMIT 1)
        WHERE current_project_id = ?
    ''', (project_id,))
    conn.commit()

    return jsonify({'message': '项目已删除'})



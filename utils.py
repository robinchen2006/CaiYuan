from functools import wraps
from flask import session, redirect, url_for, jsonify, current_app
import os
from PIL import Image

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def convert_to_progressive_jpeg(filepath):
    """
    Convert image to progressive JPEG if it's a supported image type.
    Returns the new filepath (extension might change to .jpg).
    """
    try:
        # Simple extension check
        file_ext = os.path.splitext(filepath)[1].lower()
        if file_ext not in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            return filepath

        base_name = os.path.splitext(filepath)[0]
        new_filepath = base_name + ".jpg"
        temp_filepath = base_name + ".temp.jpg"

        with Image.open(filepath) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(temp_filepath, "JPEG", quality=85, optimize=True, progressive=True)
            
        # Replace original with new file
        if filepath != new_filepath: 
            if os.path.exists(filepath):
                os.remove(filepath)
        
        if os.path.exists(new_filepath):
             os.remove(new_filepath)
             
        os.rename(temp_filepath, new_filepath)
        return new_filepath
        
    except Exception as e:
        # Log error? current_app might not be available if outside request context or not initialized
        # but utils is used in routes so usually fine.
        try:
           current_app.logger.error(f"Error converting image {filepath}: {e}")
        except:
           pass
           
        # Cleanup temp if exists
        # ...
        return filepath

def create_thumbnail(image_path, size=(300, 300)):
    """
    Generate a thumbnail for an image.
    Saves it as thumb_<filename> in the same directory.
    Returns the path to the thumbnail.
    """
    try:
        if not os.path.exists(image_path):
            return None
        
        filename = os.path.basename(image_path)
        dirname = os.path.dirname(image_path)
        thumb_filename = f"thumb_{filename}"
        thumb_path = os.path.join(dirname, thumb_filename)
        
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (e.g. for PNG with transparency if saving as JPG, though we'll keep format)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            img.thumbnail(size)
            img.save(thumb_path)
            
        return thumb_path
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return None

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function

def get_user_team_id():
    """Get current user's team_id"""
    return session.get('team_id')

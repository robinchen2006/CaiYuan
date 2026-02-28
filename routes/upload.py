from flask import Blueprint, jsonify, request, session, current_app
from utils import login_required, convert_to_progressive_jpeg
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import shutil
# from PIL import Image # No longer needed here if using utils

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/chunk', methods=['POST'])
@login_required
def upload_chunk():
    """Handle chunked file upload"""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file part'}), 400

    file_uuid = request.form.get('dzuuid')
    chunk_index = request.form.get('dzchunkindex')
    
    if not file_uuid or chunk_index is None:
        return jsonify({'error': 'Missing chunk metadata'}), 400

    # Secure uuid to prevent directory traversal
    file_uuid = secure_filename(file_uuid)
    
    # Create temp directory for this file
    temp_dir = os.path.join(current_app.config['UPLOAD_TEMP_FOLDER'], file_uuid)
    os.makedirs(temp_dir, exist_ok=True)

    # Save the chunk
    chunk_filename = f"part_{chunk_index}"
    file.save(os.path.join(temp_dir, chunk_filename))
    
    return jsonify({'message': 'Chunk uploaded successfully'})


@upload_bp.route('/merge', methods=['POST'])
@login_required
def merge_chunks():
    """Merge uploaded chunks into a single file"""
    data = request.get_json()
    file_uuid = data.get('dzuuid')
    filename = data.get('filename')
    total_chunks = data.get('dztotalchunkcount')
    
    if not file_uuid or not filename or total_chunks is None:
        return jsonify({'error': 'Missing merge metadata'}), 400
        
    file_uuid = secure_filename(file_uuid)
    filename = secure_filename(filename)
    
    temp_dir = os.path.join(current_app.config['UPLOAD_TEMP_FOLDER'], file_uuid)
    if not os.path.exists(temp_dir):
        return jsonify({'error': 'Upload session not found'}), 404
        
    # Check if all chunks exist
    for i in range(total_chunks):
        if not os.path.exists(os.path.join(temp_dir, f"part_{i}")):
            return jsonify({'error': f'Missing chunk {i}'}), 400
            
    # Create user directory if not exists
    current_username = secure_filename(session.get('username', 'shared'))
    if not current_username:
        current_username = 'user_' + str(session.get('user_id', 'unknown'))
    
    user_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], current_username)
    os.makedirs(user_folder, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    name = f"{session['user_id']}_{timestamp}_{filename}"
    filepath = os.path.join(user_folder, name)
    
    try:
        with open(filepath, 'wb') as final_file:
            for i in range(total_chunks):
                chunk_path = os.path.join(temp_dir, f"part_{i}")
                with open(chunk_path, 'rb') as chunk_file:
                    final_file.write(chunk_file.read())
                    
        # Clean up temp files
        shutil.rmtree(temp_dir)
        
        # Process image via utility function
        try:
            new_filepath = convert_to_progressive_jpeg(filepath)
            if new_filepath != filepath:
                # Update name if extension changed (e.g. png -> jpg)
                name = os.path.basename(new_filepath)
                filepath = new_filepath
        except Exception as e:
            current_app.logger.error(f'Error processing image {filename}: {str(e)}')

                # Continue without failing completely - just keep original file

        # Return the relative path for saving to DB + filename
        relative_path = f"{current_username}/{name}"
        
        return jsonify({
            'message': 'File merged successfully',
            'filename': relative_path,
            'original_filename': filename
        })
        
    except Exception as e:
        current_app.logger.error(f'Error merging file {filename}: {str(e)}')
        return jsonify({'error': 'Merge failed'}), 500

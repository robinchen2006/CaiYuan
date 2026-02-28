// Global variables
let currentGroups = [];
let selectedGroupId = null;
let selectedFiles = [];
let editSelectedFiles = [];
let editKeepImageIds = [];

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('noteDate').value = today;
    
    // Load groups
    loadGroups();
    
    // Setup form handlers
    setupFormHandlers();
    
    // Setup image selection
    setupImageSelection();
    
    // Load user info (for team display)
    loadUserInfo();
});

// ============ Sidebar Toggle for Mobile ============

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (window.innerWidth <= 768) {
        if (getComputedStyle(sidebar).display === 'none') {
            sidebar.style.display = 'block';
        } else {
            sidebar.style.display = 'none';
        }
    }
}

function toggleGroupList() {
    const groupList = document.getElementById('groupList');
    const collapseIcon = document.getElementById('collapseIcon');
    
    if (groupList.classList.contains('collapsed')) {
        groupList.classList.remove('collapsed');
        collapseIcon.textContent = '▼'; // Down means expanded
    } else {
        groupList.classList.add('collapsed');
        collapseIcon.textContent = '►'; // Right means collapsed
    }
}

// Reset sidebar visibility on resize
window.addEventListener('resize', function() {
    const sidebar = document.querySelector('.sidebar');
    if (window.innerWidth > 768) {
        sidebar.style.display = ''; // Remove inline style to revert to CSS
    } else {
         // On mobile, let it follow the toggle state or default hidden
         if (sidebar.style.display === '') {
             sidebar.style.display = 'none';
         }
    }
});

// Run on load to set initial state correctly if starting on mobile
window.addEventListener('load', function() {
    const sidebar = document.querySelector('.sidebar');
    if (window.innerWidth <= 768) {
        sidebar.style.display = 'none';
    }
});

// ============ Toast Notification ============

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast ' + type;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ============ Modal Functions ============

function showModal(modalId) {
    document.getElementById(modalId).classList.add('show');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
    
    // Clear edit modal data
    if (modalId === 'editNoteModal') {
        editSelectedFiles = [];
        editKeepImageIds = [];
        document.getElementById('editImagePreviewList').innerHTML = '';
        document.getElementById('editNoteImages').value = '';
    }
}

function showCreateGroupModal() {
    document.getElementById('newGroupName').value = '';
    showModal('createGroupModal');
}

function showEditGroupModal(groupId, groupName) {
    document.getElementById('editGroupId').value = groupId;
    document.getElementById('editGroupName').value = groupName;
    showModal('editGroupModal');
}

// ============ Tab Functions ============

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName + 'Tab').classList.add('active');
    
    // Load content if browsing
    if (tabName === 'browse') {
        loadBrowseContent();
    }
}

// ============ Group Functions ============

async function loadGroups() {
    try {
        const response = await fetch('/api/groups');
        currentGroups = await response.json();
        renderGroupList();
        updateGroupSelects();
    } catch (error) {
        showToast('加载品类失败', 'error');
    }
}

function renderGroupList() {
    const groupList = document.getElementById('groupList');
    
    if (currentGroups.length === 0) {
        groupList.innerHTML = `
            <div class="empty-state">
                <p>暂无品类</p>
                <p>点击上方按钮创建品类</p>
            </div>
        `;
        return;
    }
    
    groupList.innerHTML = currentGroups.map(group => `
        <div class="group-item ${selectedGroupId === group.id ? 'active' : ''}" 
             onclick="selectGroup(${group.id})" data-id="${group.id}">
            <span class="group-name">${escapeHtml(group.name)}</span>
            <div class="group-actions">
                <button class="action-btn" onclick="event.stopPropagation(); showEditGroupModal(${group.id}, '${escapeHtml(group.name)}')" title="编辑">
                    ✏️
                </button>
                <button class="action-btn" onclick="event.stopPropagation(); deleteGroup(${group.id})" title="删除">
                    🗑️
                </button>
            </div>
        </div>
    `).join('');
}

function updateGroupSelects() {
    const selects = ['noteGroup', 'browseGroup', 'editNoteGroup'];
    
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (!select) return;
        
        const currentValue = select.value;
        const isOptional = selectId === 'browseGroup';
        
        select.innerHTML = isOptional 
            ? '<option value="">全部品类</option>'
            : '<option value="">请选择品类</option>';
        
        currentGroups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.id;
            option.textContent = group.name;
            select.appendChild(option);
        });
        
        // Restore previous value if it still exists
        if (currentValue && currentGroups.some(g => g.id == currentValue)) {
            select.value = currentValue;
        }
    });
}

function selectGroup(groupId) {
    selectedGroupId = groupId;
    renderGroupList();
}

async function createGroup() {
    const name = document.getElementById('newGroupName').value.trim();
    
    if (!name) {
        showToast('请输入品类名称', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('品类创建成功');
            closeModal('createGroupModal');
            loadGroups();
        } else {
            showToast(data.error || '创建失败', 'error');
        }
    } catch (error) {
        showToast('创建失败', 'error');
    }
}

async function updateGroup() {
    const groupId = document.getElementById('editGroupId').value;
    const name = document.getElementById('editGroupName').value.trim();
    
    if (!name) {
        showToast('请输入品类名称', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/groups/${groupId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('品类更新成功');
            closeModal('editGroupModal');
            loadGroups();
        } else {
            showToast(data.error || '更新失败', 'error');
        }
    } catch (error) {
        showToast('更新失败', 'error');
    }
}

async function deleteGroup(groupId) {
    if (!confirm('确定要删除这个品类吗？品类内的所有笔记和图片都将被删除。')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/groups/${groupId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('品类删除成功');
            if (selectedGroupId === groupId) {
                selectedGroupId = null;
            }
            loadGroups();
            loadBrowseContent();
        } else {
            const data = await response.json();
            showToast(data.error || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
    }
}

// ============ Image Selection ============

function setupImageSelection() {
    // For creating notes
    const noteImagesInput = document.getElementById('noteImages');
    noteImagesInput.addEventListener('change', function(e) {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
                selectedFiles.push(file);
            }
        });
        renderImagePreviews();
    });
    
    // For editing notes
    const editImagesInput = document.getElementById('editNoteImages');
    editImagesInput.addEventListener('change', function(e) {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            if (!editSelectedFiles.some(f => f.name === file.name && f.size === file.size)) {
                editSelectedFiles.push(file);
            }
        });
        renderEditImagePreviews();
    });
}

function renderImagePreviews() {
    const container = document.getElementById('imagePreviewList');
    container.innerHTML = selectedFiles.map((file, index) => {
        const url = URL.createObjectURL(file);
        return `
            <div class="image-preview-item">
                <img src="${url}" alt="${escapeHtml(file.name)}">
                <button type="button" class="remove-btn" onclick="removeSelectedImage(${index})">×</button>
            </div>
        `;
    }).join('');
}

function removeSelectedImage(index) {
    selectedFiles.splice(index, 1);
    renderImagePreviews();
}

function renderEditImagePreviews() {
    const container = document.getElementById('editImagePreviewList');
    container.innerHTML = editSelectedFiles.map((file, index) => {
        const url = URL.createObjectURL(file);
        return `
            <div class="image-preview-item">
                <img src="${url}" alt="${escapeHtml(file.name)}">
                <button type="button" class="remove-btn" onclick="removeEditSelectedImage(${index})">×</button>
            </div>
        `;
    }).join('');
}

function removeEditSelectedImage(index) {
    editSelectedFiles.splice(index, 1);
    renderEditImagePreviews();
}


// ============ Chunked Upload ============

function generateUUID() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

async function uploadChunkedFile(file, onProgress) {
    const CHUNK_SIZE = 4 * 1024 * 1024; // 4MB Chunk
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    
    // UUID for this file upload session
    const fileUuid = generateUUID();
    
    for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(file.size, start + CHUNK_SIZE);
        const chunk = file.slice(start, end);
        
        const chunkFormData = new FormData();
        chunkFormData.append('file', chunk);
        chunkFormData.append('dzuuid', fileUuid);
        chunkFormData.append('dzchunkindex', i);
        chunkFormData.append('dztotalchunkcount', totalChunks); // Ensure consistent casing
        
        try {
            const response = await fetch('/api/upload/chunk', {
                method: 'POST',
                body: chunkFormData
            });
            
            if (!response.ok) {
                throw new Error(`Upload failed for chunk ${i}`);
            }
            
            if (onProgress) {
                onProgress((i + 1) / totalChunks * 100);
            }
        } catch (error) {
            console.error('Chunk upload error:', error);
            throw error;
        }
    }
    
    // Merge
    const mergeResponse = await fetch('/api/upload/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            dzuuid: fileUuid,
            filename: file.name,
            dztotalchunkcount: totalChunks
        })
    });
    
    if (!mergeResponse.ok) {
        throw new Error('Merge failed');
    }
    
    return await mergeResponse.json();
}

/**
 * Process files for upload, using chunked upload for large files or large batches.
 * @param {File[]} files - List of files to process
 * @returns {Promise<{uploadedChunks: any[], smallFiles: File[]}>}
 */
async function processFilesForUpload(files) {
    const CHUNK_THRESHOLD = 5 * 1024 * 1024; // 5MB
    const MAX_BATCH_SIZE = 10 * 1024 * 1024; // 10MB limit for non-chunked batch
    const uploadedChunks = [];
    const smallFiles = [];
    let totalSmallSize = 0;

    for (const file of files) {
        // Determine if we should chunk this file
        // 1. It is individually large (>5MB)
        // 2. OR adding it to the batch would exceed the safe batch size
        if (file.size > CHUNK_THRESHOLD || (totalSmallSize + file.size > MAX_BATCH_SIZE)) {
            showToast(`正在分块上传: ${file.name}...`, 'info');
            // This might throw, caller should handle try/catch
            const result = await uploadChunkedFile(file);
            uploadedChunks.push(result);
        } else {
            smallFiles.push(file);
            totalSmallSize += file.size;
        }
    }
    
    return { uploadedChunks, smallFiles };
}

// ============ Form Handlers ============

function setupFormHandlers() {
    // Note form
    document.getElementById('noteForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const content = document.getElementById('noteContent').value.trim();
        const date = document.getElementById('noteDate').value;
        const groupId = document.getElementById('noteGroup').value;
        
        if (!content && selectedFiles.length === 0) {
            showToast('请输入笔记内容或上传图片', 'error');
            return;
        }
        
        if (!groupId) {
            showToast('请选择品类', 'error');
            return;
        }
        
        const submitButton = document.querySelector('#noteForm button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.textContent = '上传中...';
        
        try {
            // Process files (using shared chunked logic)
            const { uploadedChunks, smallFiles } = await processFilesForUpload(selectedFiles);
            
            const formData = new FormData();
            formData.append('content', content);
            formData.append('date', date);
            formData.append('group_id', groupId);
            formData.append('uploaded_chunks', JSON.stringify(uploadedChunks));
            
            smallFiles.forEach(file => {
                formData.append('images', file);
            });
            
            const response = await fetch('/api/notes', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showToast('笔记保存成功');
                document.getElementById('noteContent').value = '';
                document.getElementById('noteImages').value = '';
                selectedFiles = [];
                renderImagePreviews();
            } else {
                showToast(data.error || '保存失败', 'error');
            }
        } catch (error) {
            showToast('保存失败: ' + error.message, 'error');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
        }
    });
}

// ============ Browse Functions ============

async function loadBrowseContent() {
    const groupId = document.getElementById('browseGroup').value;
    await loadNotes(groupId);
}

async function loadNotes(groupId) {
    try {
        let url = '/api/notes';
        if (groupId) {
            url += `?group_id=${groupId}`;
        }
        
        const response = await fetch(url);
        const notes = await response.json();
        renderNotes(notes);
    } catch (error) {
        showToast('加载笔记失败', 'error');
    }
}

function renderNotes(notes) {
    const notesList = document.getElementById('notesList');
    
    if (notes.length === 0) {
        notesList.innerHTML = `
            <div class="empty-state">
                <p>暂无笔记</p>
                <p>切换到"记录笔记"标签创建新笔记</p>
            </div>
        `;
        return;
    }
    
    notesList.innerHTML = notes.map(note => {
        const imagesHtml = note.images && note.images.length > 0 
            ? `<div class="note-card-images">
                ${note.images.map(img => `
                    <div class="note-image-item" onclick="showImageModal('/static/uploads/${img.filename}', '${escapeHtml(img.original_filename)}')">
                        <img src="/static/uploads/${img.filename}" alt="${escapeHtml(img.original_filename)}">
                    </div>
                `).join('')}
               </div>`
            : '';
        
        const authorHtml = note.author ? `<span>👤 ${escapeHtml(note.author)}</span>` : '';
        
        return `
            <div class="note-card" data-id="${note.id}">
                <div class="note-card-header">
                    <div class="note-card-meta">
                        <span>📅 ${note.date}</span>
                        <span>📁 ${escapeHtml(note.group_name)}</span>
                        ${authorHtml}
                    </div>
                    <div class="note-card-actions">
                        <button class="btn btn-sm btn-outline" onclick="showEditNoteModal(${note.id})">编辑</button>
                    </div>
                </div>
                <div class="note-card-body">
                    <div class="note-card-content">${escapeHtml(note.content)}</div>
                    ${imagesHtml}
                </div>
            </div>
        `;
    }).join('');
}

// ============ Note CRUD ============

async function showEditNoteModal(noteId) {
    try {
        const response = await fetch('/api/notes');
        const notes = await response.json();
        const note = notes.find(n => n.id === noteId);
        
        if (note) {
            document.getElementById('editNoteId').value = note.id;
            document.getElementById('editNoteDate').value = note.date;
            document.getElementById('editNoteGroup').value = note.group_id;
            document.getElementById('editNoteContent').value = note.content;
            
            // Reset edit state
            editSelectedFiles = [];
            editKeepImageIds = note.images ? note.images.map(img => img.id) : [];
            
            // Show existing images
            renderExistingImages(note.images || []);
            renderEditImagePreviews();
            
            showModal('editNoteModal');
        }
    } catch (error) {
        showToast('加载笔记失败', 'error');
    }
}

function renderExistingImages(images) {
    const container = document.getElementById('editExistingImages');
    
    if (images.length === 0) {
        container.innerHTML = '<p style="color: #6c757d;">暂无图片</p>';
        return;
    }
    
    container.innerHTML = images.map(img => {
        const isKept = editKeepImageIds.includes(img.id);
        return `
            <div class="existing-image-item ${isKept ? '' : 'removed'}" data-id="${img.id}">
                <img src="/static/uploads/${img.filename}" alt="${escapeHtml(img.original_filename)}">
                <button type="button" class="remove-btn" onclick="toggleExistingImage(${img.id})">${isKept ? '×' : '+'}</button>
            </div>
        `;
    }).join('');
}

function toggleExistingImage(imageId) {
    const index = editKeepImageIds.indexOf(imageId);
    if (index > -1) {
        editKeepImageIds.splice(index, 1);
    } else {
        editKeepImageIds.push(imageId);
    }
    
    // Update UI
    const item = document.querySelector(`.existing-image-item[data-id="${imageId}"]`);
    if (item) {
        const isKept = editKeepImageIds.includes(imageId);
        item.classList.toggle('removed', !isKept);
        item.querySelector('.remove-btn').textContent = isKept ? '×' : '+';
    }
}

async function updateNote() {
    const noteId = document.getElementById('editNoteId').value;
    const content = document.getElementById('editNoteContent').value.trim();
    const date = document.getElementById('editNoteDate').value;
    const groupId = document.getElementById('editNoteGroup').value;
    
    if (!content && editKeepImageIds.length === 0 && editSelectedFiles.length === 0) {
        showToast('请输入笔记内容或保留/添加图片', 'error');
        return;
    }
    
    if (!groupId) {
        showToast('请选择品类', 'error');
        return;
    }
    
    const submitButton = document.querySelector('#editNoteModal .btn-primary'); // Assuming it's the primary button
    const originalButtonText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = '更新中...';
    
    try {
        // Process new files (using shared chunked logic)
        const { uploadedChunks, smallFiles } = await processFilesForUpload(editSelectedFiles);
        
        const formData = new FormData();
        formData.append('content', content);
        formData.append('date', date);
        formData.append('group_id', groupId);
        formData.append('keep_images', JSON.stringify(editKeepImageIds));
        formData.append('uploaded_chunks', JSON.stringify(uploadedChunks));
        
        smallFiles.forEach(file => {
            formData.append('images', file);
        });
        
        const response = await fetch(`/api/notes/${noteId}`, {
            method: 'PUT',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('笔记更新成功');
            closeModal('editNoteModal');
            loadBrowseContent();
        } else {
            showToast(data.error || '更新失败', 'error');
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
    }
}

async function deleteCurrentNote() {
    const noteId = document.getElementById('editNoteId').value;
    if (noteId) {
        const success = await deleteNote(noteId);
        if (success) {
            closeModal('editNoteModal');
        }
    }
}

async function deleteNote(noteId) {
    if (!confirm('确定要删除这条笔记吗？关联的图片也将被删除。')) {
        return false;
    }
    
    try {
        const response = await fetch(`/api/notes/${noteId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('笔记删除成功');
            loadBrowseContent();
            return true;
        } else {
            const data = await response.json();
            showToast(data.error || '删除失败', 'error');
            return false;
        }
    } catch (error) {
        showToast('删除失败', 'error');
        return false;
    }
}

// ============ Image Modal ============

function showImageModal(src, title) {
    document.getElementById('modalImage').src = src;
    document.getElementById('imageModalTitle').textContent = title;
    showModal('imageModal');
}

// ============ Utility Functions ============

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modals on outside click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        const modalId = e.target.id;
        closeModal(modalId);
    }
});

// Close modals on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.show').forEach(modal => {
            closeModal(modal.id);
        });
    }
});

// ============ User Info ============

async function loadUserInfo() {
    try {
        const response = await fetch('/api/user/info');
        const user = await response.json();
        
        if (user.team_name) {
            const teamBadge = document.getElementById('teamBadge');
            if (teamBadge) {
                teamBadge.textContent = `用户组: ${user.team_name}`;
                teamBadge.style.display = 'inline-block';
            }
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
    }
}

// ============ Password Change ============

function showChangePasswordModal() {
    document.getElementById('oldPassword').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmNewPassword').value = '';
    showModal('changePasswordModal');
}

async function changePassword() {
    const oldPassword = document.getElementById('oldPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmNewPassword = document.getElementById('confirmNewPassword').value;
    
    if (!oldPassword || !newPassword || !confirmNewPassword) {
        showToast('请填写所有字段', 'error');
        return;
    }
    
    if (newPassword !== confirmNewPassword) {
        showToast('两次新密码不一致', 'error');
        return;
    }
    
    if (newPassword.length < 4) {
        showToast('新密码至少需要4个字符', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('密码修改成功');
            closeModal('changePasswordModal');
        } else {
            showToast(data.error || '修改失败', 'error');
        }
    } catch (error) {
        showToast('修改失败', 'error');
    }
}

// ============ Admin Functions ============

// Tab switching for admin
const originalSwitchTab = switchTab;
switchTab = function(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName + 'Tab').classList.add('active');
    
    // Load content
    if (tabName === 'browse') {
        loadBrowseContent();
    } else if (tabName === 'admin') {
        loadAdminData();
    }
};

async function loadAdminData() {
    await Promise.all([
        loadPendingUsers(),
        loadTeams(),
        loadAllUsers()
    ]);
}

// ============ Pending Users ============

async function loadPendingUsers() {
    try {
        const response = await fetch('/api/admin/users/pending');
        if (!response.ok) return;
        
        const users = await response.json();
        renderPendingUsers(users);
    } catch (error) {
        console.error('Failed to load pending users:', error);
    }
}

function renderPendingUsers(users) {
    const container = document.getElementById('pendingUsersList');
    if (!container) return;
    
    if (users.length === 0) {
        container.innerHTML = '<p class="empty-text">暂无待审核用户</p>';
        return;
    }
    
    container.innerHTML = users.map(user => `
        <div class="pending-user-item">
            <div class="user-info">
                <strong>${escapeHtml(user.username)}</strong>
                <span class="user-time">${user.created_at}</span>
            </div>
            <div class="user-actions">
                <button class="btn btn-sm btn-primary" onclick="approveUser(${user.id})">通过</button>
                <button class="btn btn-sm btn-danger" onclick="rejectUser(${user.id})">拒绝</button>
            </div>
        </div>
    `).join('');
}

async function approveUser(userId) {
    try {
        const response = await fetch(`/api/admin/users/${userId}/approve`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showToast('用户已通过审核');
            loadAdminData();
        } else {
            const data = await response.json();
            showToast(data.error || '操作失败', 'error');
        }
    } catch (error) {
        showToast('操作失败', 'error');
    }
}

async function rejectUser(userId) {
    if (!confirm('确定要拒绝此用户吗？')) return;
    
    try {
        const response = await fetch(`/api/admin/users/${userId}/reject`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showToast('用户已被拒绝');
            loadAdminData();
        } else {
            const data = await response.json();
            showToast(data.error || '操作失败', 'error');
        }
    } catch (error) {
        showToast('操作失败', 'error');
    }
}

// ============ User Teams ============

let allTeams = [];

async function loadTeams() {
    try {
        const response = await fetch('/api/admin/teams');
        if (!response.ok) return;
        
        allTeams = await response.json();
        renderTeams(allTeams);
    } catch (error) {
        console.error('Failed to load teams:', error);
    }
}

function renderTeams(teams) {
    const container = document.getElementById('teamsList');
    if (!container) return;
    
    if (teams.length === 0) {
        container.innerHTML = '<p class="empty-text">暂无用户组</p>';
        return;
    }
    
    container.innerHTML = teams.map(team => `
        <div class="team-item">
            <div class="team-info">
                <strong>${escapeHtml(team.name)}</strong>
                <span class="team-count">${team.member_count} 成员</span>
            </div>
            <div class="team-actions">
                <button class="btn btn-sm btn-outline" onclick="editTeam(${team.id}, '${escapeHtml(team.name)}')">编辑</button>
                <button class="btn btn-sm btn-danger" onclick="deleteTeam(${team.id})">删除</button>
            </div>
        </div>
    `).join('');
}

function showCreateTeamModal() {
    document.getElementById('newTeamName').value = '';
    showModal('createTeamModal');
}

async function createTeam() {
    const name = document.getElementById('newTeamName').value.trim();
    
    if (!name) {
        showToast('请输入用户组名称', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/admin/teams', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('用户组创建成功');
            closeModal('createTeamModal');
            loadAdminData();
        } else {
            showToast(data.error || '创建失败', 'error');
        }
    } catch (error) {
        showToast('创建失败', 'error');
    }
}

async function editTeam(teamId, currentName) {
    const newName = prompt('请输入新的用户组名称', currentName);
    if (!newName || newName.trim() === currentName) return;
    
    try {
        const response = await fetch(`/api/admin/teams/${teamId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName.trim() })
        });
        
        if (response.ok) {
            showToast('用户组更新成功');
            loadAdminData();
        } else {
            const data = await response.json();
            showToast(data.error || '更新失败', 'error');
        }
    } catch (error) {
        showToast('更新失败', 'error');
    }
}

async function deleteTeam(teamId) {
    if (!confirm('确定要删除此用户组吗？组内用户将被移出该组。')) return;
    
    try {
        const response = await fetch(`/api/admin/teams/${teamId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('用户组已删除');
            loadAdminData();
        } else {
            const data = await response.json();
            showToast(data.error || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
    }
}

// ============ All Users ============

async function loadAllUsers() {
    try {
        const response = await fetch('/api/admin/users');
        if (!response.ok) return;
        
        const users = await response.json();
        renderAllUsers(users);
    } catch (error) {
        console.error('Failed to load users:', error);
    }
}

function renderAllUsers(users) {
    const tbody = document.querySelector('#usersTable tbody');
    if (!tbody) return;
    
    const statusMap = {
        'pending': '<span class="status-badge pending">待审核</span>',
        'approved': '<span class="status-badge approved">已通过</span>',
        'rejected': '<span class="status-badge rejected">已拒绝</span>'
    };
    
    tbody.innerHTML = users.map(user => `
        <tr>
            <td>${escapeHtml(user.username)}</td>
            <td>${user.role === 'admin' ? '<span class="role-badge admin">管理员</span>' : '用户'}</td>
            <td>${statusMap[user.status] || user.status}</td>
            <td>${user.team_name || '<span class="no-team">无</span>'}</td>
            <td>${user.created_at}</td>
            <td>
                ${user.role !== 'admin' ? `
                    <button class="btn btn-xs btn-outline" onclick="showAssignTeamModal(${user.id}, '${escapeHtml(user.username)}', ${user.team_id || 'null'})">分配组</button>
                    <button class="btn btn-xs btn-danger" onclick="deleteUser(${user.id})">删除</button>
                ` : ''}
            </td>
        </tr>
    `).join('');
}

function showAssignTeamModal(userId, username, currentTeamId) {
    document.getElementById('assignUserId').value = userId;
    document.getElementById('assignUserName').textContent = `为用户 "${username}" 分配用户组:`;
    
    const select = document.getElementById('assignTeamSelect');
    select.innerHTML = '<option value="">无用户组</option>';
    
    allTeams.forEach(team => {
        const option = document.createElement('option');
        option.value = team.id;
        option.textContent = team.name;
        if (team.id === currentTeamId) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    
    showModal('assignTeamModal');
}

async function assignTeam() {
    const userId = document.getElementById('assignUserId').value;
    const teamId = document.getElementById('assignTeamSelect').value || null;
    
    try {
        const response = await fetch(`/api/admin/users/${userId}/team`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ team_id: teamId ? parseInt(teamId) : null })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('用户组分配成功');
            closeModal('assignTeamModal');
            loadAdminData();
        } else {
            showToast(data.error || '分配失败', 'error');
        }
    } catch (error) {
        showToast('分配失败', 'error');
    }
}

async function deleteUser(userId) {
    if (!confirm('确定要删除此用户吗？')) return;
    
    try {
        const response = await fetch(`/api/admin/users/${userId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('用户已删除');
            loadAdminData();
        } else {
            const data = await response.json();
            showToast(data.error || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
    }
}
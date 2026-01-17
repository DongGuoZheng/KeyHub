// DOM Elements
const adminsTableBody = document.querySelector('#adminsTable tbody');
const emptyState = document.getElementById('emptyState');
const refreshBtn = document.getElementById('refreshBtn');
const addAdminBtn = document.getElementById('addAdminBtn');

// Modals
const addAdminModal = document.getElementById('addAdminModal');
const editUsernameModal = document.getElementById('editUsernameModal');
const changePasswordModal = document.getElementById('changePasswordModal');
const closeButtons = document.querySelectorAll('.close, .close-btn');

// Forms
const addAdminForm = document.getElementById('addAdminForm');
const editUsernameForm = document.getElementById('editUsernameForm');
const changePasswordForm = document.getElementById('changePasswordForm');

// API Helper Functions
function getHeaders() {
    const headers = {
        'Content-Type': 'application/json'
    };
    const token = localStorage.getItem('adminToken');
    if (token) {
        headers['X-Admin-Token'] = token;
    }
    return headers;
}

async function apiRequest(url, options = {}) {
    try {
        const res = await fetch(url, {
            ...options,
            headers: {
                ...getHeaders(),
                ...options.headers
            }
        });

        // Handle unauthorized
        if (res.status === 401) {
            localStorage.removeItem('adminToken');
            window.location.href = '/login';
            throw new Error('未授权，请重新登录');
        }

        return res;
    } catch (error) {
        if (error.message.includes('未授权')) {
            throw error;
        }
        throw new Error('网络请求失败');
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    loadAdmins();
    setupEventListeners();
});

function setupEventListeners() {
    // Logout
    document.getElementById('logoutBtn').addEventListener('click', () => {
        localStorage.removeItem('adminToken');
        window.location.href = '/login';
    });

    // Toolbar
    refreshBtn.addEventListener('click', loadAdmins);
    addAdminBtn.addEventListener('click', () => openModal(addAdminModal));

    // Forms
    addAdminForm.addEventListener('submit', handleAddAdmin);
    editUsernameForm.addEventListener('submit', handleEditUsername);
    changePasswordForm.addEventListener('submit', handleChangePassword);

    // Modals
    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            closeModal(btn.closest('.modal'));
        });
    });

    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            closeModal(e.target);
        }
    });
}

// --- Admins Logic ---

async function loadAdmins() {
    try {
        adminsTableBody.innerHTML = '<tr><td colspan="3" style="text-align:center">加载中...</td></tr>';

        const res = await apiRequest('/api/admin/users');
        const admins = await res.json();

        renderAdmins(admins);
    } catch (e) {
        console.error(e);
        showToast('加载管理员列表失败');
    }
}

function renderAdmins(admins) {
    adminsTableBody.innerHTML = '';

    if (admins.length === 0) {
        emptyState.style.display = 'block';
        return;
    }
    emptyState.style.display = 'none';

    admins.forEach(admin => {
        const tr = document.createElement('tr');
        const createdDate = new Date(admin.created_at).toLocaleString();

        tr.innerHTML = `
            <td><strong>${admin.username}</strong></td>
            <td>${createdDate}</td>
            <td class="actions-cell">
               <!-- To be filled by JS for event binding safely -->
            </td>
        `;

        // Actions
        const actionsTd = tr.querySelector('.actions-cell');

        const editUsernameBtn = createBtn('修改用户名', () => openEditUsernameModal(admin));
        const changePasswordBtn = createBtn('修改密码', () => openChangePasswordModal(admin));
        const deleteBtn = createBtn('删除', () => deleteAdmin(admin), true);

        actionsTd.appendChild(editUsernameBtn);
        actionsTd.appendChild(changePasswordBtn);
        actionsTd.appendChild(deleteBtn);

        adminsTableBody.appendChild(tr);
    });
}

function createBtn(text, onClick, isDanger = false) {
    const btn = document.createElement('button');
    btn.className = 'action-btn ' + (isDanger ? 'delete' : '');
    btn.textContent = text;
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onClick();
    });
    return btn;
}

// --- Add Admin ---

async function handleAddAdmin(e) {
    e.preventDefault();

    const username = document.getElementById('addUsername').value;
    const password = document.getElementById('addPassword').value;

    try {
        const res = await apiRequest('/api/admin/users', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        closeModal(addAdminModal);
        showToast('管理员创建成功');
        loadAdmins();
        addAdminForm.reset();
    } catch (e) {
        showToast(e.message);
    }
}

// --- Edit Username ---

function openEditUsernameModal(admin) {
    document.getElementById('editOldUsername').value = admin.username;
    document.getElementById('editCurrentUsername').value = admin.username;
    document.getElementById('editNewUsername').value = '';
    openModal(editUsernameModal);
}

async function handleEditUsername(e) {
    e.preventDefault();

    const oldUsername = document.getElementById('editOldUsername').value;
    const newUsername = document.getElementById('editNewUsername').value;

    try {
        const res = await apiRequest(`/api/admin/users/${oldUsername}`, {
            method: 'PUT',
            body: JSON.stringify({ new_username: newUsername })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        closeModal(editUsernameModal);
        showToast('用户名已更新');
        loadAdmins();
    } catch (e) {
        showToast(e.message);
    }
}

// --- Change Password ---

function openChangePasswordModal(admin) {
    document.getElementById('changePasswordUsername').value = admin.username;
    document.getElementById('changePasswordUsernameDisplay').value = admin.username;
    document.getElementById('changeNewPassword').value = '';
    openModal(changePasswordModal);
}

async function handleChangePassword(e) {
    e.preventDefault();

    const username = document.getElementById('changePasswordUsername').value;
    const newPassword = document.getElementById('changeNewPassword').value;

    try {
        const res = await apiRequest(`/api/admin/users/${username}/password`, {
            method: 'PUT',
            body: JSON.stringify({ new_password: newPassword })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        closeModal(changePasswordModal);
        showToast('密码已更新');
    } catch (e) {
        showToast(e.message);
    }
}

// --- Delete Admin ---

async function deleteAdmin(admin) {
    if (!confirm(`确定要删除管理员 "${admin.username}" 吗？`)) return;

    try {
        const res = await apiRequest(`/api/admin/users/${admin.username}`, {
            method: 'DELETE'
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        showToast('管理员已删除');
        loadAdmins();
    } catch (e) {
        showToast(e.message);
    }
}

// --- Helpers ---

function openModal(modal) {
    modal.style.display = 'flex';
    // Trigger reflow for transition
    setTimeout(() => modal.classList.add('show'), 10);
}

function closeModal(modal) {
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

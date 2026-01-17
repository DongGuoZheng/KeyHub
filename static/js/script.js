// DOM Elements
const projectSelect = document.getElementById('projectSelect');
const addProjectBtn = document.getElementById('addProjectBtn');
const editProjectBtn = document.getElementById('editProjectBtn');
const deleteProjectBtn = document.getElementById('deleteProjectBtn');
const projectDesc = document.getElementById('projectDesc');

const statsTotal = document.getElementById('statsTotal');
const statsActive = document.getElementById('statsActive');
const statsBound = document.getElementById('statsBound');

const refreshBtn = document.getElementById('refreshBtn');
const generateKeyBtn = document.getElementById('generateKeyBtn');
const keysTableBody = document.querySelector('#keysTable tbody');
const emptyState = document.getElementById('emptyState');

// Modals
const projectModal = document.getElementById('projectModal');
const keyModal = document.getElementById('keyModal');
const bindingsModal = document.getElementById('bindingsModal');
const closeButtons = document.querySelectorAll('.close, .close-btn');

// Forms
const projectForm = document.getElementById('projectForm');
const keyForm = document.getElementById('keyForm');

// State
let currentProject = null;
let projects = [];

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
    loadProjects();
    setupEventListeners();
});

function setupEventListeners() {
    // Logout
    document.getElementById('logoutBtn').addEventListener('click', () => {
        localStorage.removeItem('adminToken');
        window.location.href = '/login';
    });

    // Project interactions
    projectSelect.addEventListener('change', (e) => {
        selectProject(e.target.value);
    });

    addProjectBtn.addEventListener('click', () => {
        openProjectModal();
    });

    editProjectBtn.addEventListener('click', () => {
        if (currentProject) openProjectModal(currentProject);
    });

    deleteProjectBtn.addEventListener('click', deleteCurrentProject);

    // Toolbar
    refreshBtn.addEventListener('click', loadKeys);
    generateKeyBtn.addEventListener('click', () => {
        if (!currentProject) return showToast('请先选择一个项目');
        openModal(keyModal);
    });

    // Forms
    projectForm.addEventListener('submit', handleProjectSubmit);
    keyForm.addEventListener('submit', handleKeySubmit);

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

// --- Projects Logic ---

async function loadProjects() {
    try {
        const res = await apiRequest('/api/projects');
        projects = await res.json();

        projectSelect.innerHTML = '';
        projects.forEach(p => {
            const option = document.createElement('option');
            option.value = p.id;
            option.textContent = p.name;
            projectSelect.appendChild(option);
        });

        if (projects.length > 0) {
            // Restore selection or pick first
            // For now pick first if not set
            if (!currentProject) {
                selectProject(projects[0].id);
            } else {
                // Check if current still exists
                const exists = projects.find(p => p.id == currentProject.id);
                if (exists) selectProject(exists.id);
                else selectProject(projects[0].id);
            }
        }
    } catch (e) {
        console.error('Failed to load projects', e);
        showToast('加载项目失败');
    }
}

function selectProject(id) {
    currentProject = projects.find(p => p.id == id);
    if (!currentProject) return;

    projectSelect.value = id;
    projectDesc.textContent = currentProject.description || '无描述';

    // Default project protection
    if (currentProject.is_default) {
        deleteProjectBtn.style.display = 'none';
    } else {
        deleteProjectBtn.style.display = 'inline-block';
    }

    loadKeys();
}

async function handleProjectSubmit(e) {
    e.preventDefault();
    const id = document.getElementById('projectId').value;
    const name = document.getElementById('projectName').value;
    const desc = document.getElementById('projectDescInput').value;

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/projects/${id}` : '/api/projects';

    try {
        const res = await apiRequest(url, {
            method,
            body: JSON.stringify({ name, description: desc })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        closeModal(projectModal);
        showToast(id ? '项目已更新' : '项目已创建');
        loadProjects(); // Reloads and re-selects
    } catch (e) {
        showToast(e.message);
    }
}

async function deleteCurrentProject() {
    if (!currentProject || currentProject.is_default) return;
    if (!confirm(`确定删除项目 "${currentProject.name}" 及其所有密钥吗？`)) return;

    try {
        const res = await apiRequest(`/api/projects/${currentProject.id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        showToast('项目已删除');
        currentProject = null;
        loadProjects();
    } catch (e) {
        showToast(e.message);
    }
}

// --- Keys Logic ---

async function loadKeys() {
    if (!currentProject) return;

    try {
        keysTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center">Loading...</td></tr>';

        const res = await apiRequest(`/api/keys?project_id=${currentProject.id}`);
        const keys = await res.json();

        renderKeys(keys);
        updateStats(keys);
    } catch (e) {
        console.error(e);
        showToast('加载密钥失败');
    }
}

function renderKeys(keys) {
    keysTableBody.innerHTML = '';

    if (keys.length === 0) {
        emptyState.style.display = 'block';
        return;
    }
    emptyState.style.display = 'none';

    keys.forEach(key => {
        const tr = document.createElement('tr');
        const createdDate = new Date(key.created_at).toLocaleString();

        const statusClass = key.is_active ? 'status-active' : 'status-disabled';
        const statusText = key.is_active ? '已激活' : '已禁用';

        tr.innerHTML = `
            <td data-label="密钥"><span class="key-mono">${key.key}</span></td>
            <td data-label="状态"><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td data-label="备注">${key.remarks || '-'}</td>
            <td data-label="绑定数">${key.binding_count}</td>
            <td data-label="创建时间">${createdDate}</td>
            <td class="actions-cell" data-label="操作">
               <!-- To be filled by JS for event binding safely -->
            </td>
        `;

        // Actions
        const actionsTd = tr.querySelector('.actions-cell');

        const copyBtn = createBtn('复制', () => {
            navigator.clipboard.writeText(key.key);
            showToast('密钥已复制到剪贴板');
        });

        const bindBtn = createBtn('绑定', () => openBindingsModal(key));

        const toggleBtn = createBtn(key.is_active ? '禁用' : '启用', () => toggleKey(key));

        const delBtn = createBtn('删除', () => deleteKey(key), true);

        actionsTd.appendChild(copyBtn);
        actionsTd.appendChild(bindBtn);
        actionsTd.appendChild(toggleBtn);
        actionsTd.appendChild(delBtn);

        keysTableBody.appendChild(tr);
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

function updateStats(keys) {
    statsTotal.textContent = keys.length;
    statsActive.textContent = keys.filter(k => k.is_active).length;
    // For bound keys, we count keys that have > 0 bindings
    statsBound.textContent = keys.filter(k => k.binding_count > 0).length;
}

async function handleKeySubmit(e) {
    e.preventDefault();
    if (!currentProject) return;

    const remarks = document.getElementById('keyRemarks').value;

    try {
        const res = await apiRequest('/api/keys', {
            method: 'POST',
            body: JSON.stringify({
                project_id: currentProject.id,
                remarks
            })
        });

        const data = await res.json();
        if (data.error) throw new Error(data.error);

        closeModal(keyModal);
        showToast('密钥生成成功');
        loadKeys();
        document.getElementById('keyRemarks').value = ''; // Reset
    } catch (e) {
        showToast(e.message);
    }
}

async function deleteKey(key) {
    if (!confirm('确定要删除此密钥吗？')) return;

    try {
        const res = await apiRequest(`/api/keys/${key.key}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast('密钥已删除');
            loadKeys();
        }
    } catch (e) {
        showToast('删除密钥失败');
    }
}

async function toggleKey(key) {
    try {
        const res = await apiRequest(`/api/keys/${key.key}/status`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: !key.is_active })
        });

        const data = await res.json();
        if (data.success) {
            showToast(`密钥已${!key.is_active ? '启用' : '禁用'}`);
            loadKeys();
        }
    } catch (e) {
        showToast('更新状态失败');
    }
}

// --- Bindings Logic ---

async function openBindingsModal(key) {
    document.getElementById('bindingKeyTitle').textContent = `所属密钥: ${key.key}`;
    const list = document.getElementById('bindingsList');
    list.innerHTML = '加载中...';

    openModal(bindingsModal);

    try {
        const res = await apiRequest(`/api/keys/${key.key}/bindings`);
        const bindings = await res.json();

        list.innerHTML = '';
        if (bindings.length === 0) {
            list.innerHTML = '<div style="color:var(--text-secondary); text-align:center; padding:1rem">暂无机器绑定。</div>';
            return;
        }

        bindings.forEach(b => {
            const div = document.createElement('div');
            div.className = 'binding-item';
            div.innerHTML = `
                <div class="binding-info">
                    <div class="binding-machine-id">${b.machine_id} <span class="binding-remarks">${b.remarks || ''}</span></div>
                    <div class="binding-date">绑定时间: ${new Date(b.bound_at).toLocaleString()}</div>
                </div>
                <button class="action-btn delete" onclick="unbindMachine(${b.id}, '${key.key}')">解绑</button>
             `;
            list.appendChild(div);
        });

    } catch (e) {
        list.innerHTML = '加载绑定列表失败';
    }
}

// Make unbind accessible globally for onclick HTML attribute
window.unbindMachine = async function (id, keyVal) {
    if (!confirm('确定解绑此机器吗？')) return;

    try {
        const res = await apiRequest(`/api/bindings/${id}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('机器已解绑');
            // Refresh modal content. Since we don't pass full key obj easily,
            // we can just re-fetch using keyVal or close/refresh parent.
            // Let's refetch by calling openBindingsModal-like logic or just closing.
            // Better user experience: remove element or reload list.
            // Im implementing simple reload:
            openBindingsModal({ key: keyVal }); // Hacky but works since we only need key.key
            loadKeys(); // Refresh main table count
        }
    } catch (e) {
        showToast('解绑失败');
    }
}

// --- Helpers ---

function openProjectModal(project = null) {
    const title = document.getElementById('projectModalTitle');
    const idInput = document.getElementById('projectId');
    const nameInput = document.getElementById('projectName');
    const descInput = document.getElementById('projectDescInput');

    if (project) {
        title.textContent = '编辑项目';
        idInput.value = project.id;
        nameInput.value = project.name;
        descInput.value = project.description;
    } else {
        title.textContent = '新建项目';
        idInput.value = '';
        nameInput.value = '';
        descInput.value = '';
    }

    openModal(projectModal);
}

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

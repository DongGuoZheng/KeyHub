// DOM Elements
const projectSelect = document.getElementById('projectSelect');
const addProjectBtn = document.getElementById('addProjectBtn');
const editProjectBtn = document.getElementById('editProjectBtn');
const copyProjectNameBtn = document.getElementById('copyProjectNameBtn');
const deleteProjectBtn = document.getElementById('deleteProjectBtn');
const projectDesc = document.getElementById('projectDesc');

const statsTotal = document.getElementById('statsTotal');
const statsActive = document.getElementById('statsActive');
const statsBound = document.getElementById('statsBound');

const refreshBtn = document.getElementById('refreshBtn');
const generateKeyBtn = document.getElementById('generateKeyBtn');
const keysTableBody = document.querySelector('#keysTable tbody');
const emptyState = document.getElementById('emptyState');
const keyHeader = document.getElementById('keyHeader');
const keyModalTitle = document.getElementById('keyModalTitle');
const customKeyLabel = document.getElementById('customKeyLabel');
const customKeyInput = document.getElementById('customKeyInput');
const keySubmitBtn = document.getElementById('keySubmitBtn');

// Modals
const projectModal = document.getElementById('projectModal');
const keyModal = document.getElementById('keyModal');
const entitlementModal = document.getElementById('entitlementModal');
const remarksModal = document.getElementById('remarksModal');
const sessionsModal = document.getElementById('sessionsModal');
const closeButtons = document.querySelectorAll('.close, .close-btn');

// Forms
const projectForm = document.getElementById('projectForm');
const keyForm = document.getElementById('keyForm');
const entitlementForm = document.getElementById('entitlementForm');
const remarksForm = document.getElementById('remarksForm');
const authTypeInput = document.getElementById('authTypeInput');
const remainingPlaysGroup = document.getElementById('remainingPlaysGroup');
const addPlaysGroup = document.getElementById('addPlaysGroup');
const validUntilGroup = document.getElementById('validUntilGroup');

// State
let currentProject = null;
let projects = [];

const projectTypeLabels = {
    account: '账号管理',
    activation: '激活码授权管理',
    playback: '播控管理'
};

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

    copyProjectNameBtn.addEventListener('click', async () => {
        if (!currentProject) return showToast('请先选择一个项目');
        try {
            await navigator.clipboard.writeText(currentProject.name);
            showToast('项目名称已复制');
        } catch (e) {
            showToast('复制失败，请检查浏览器权限');
        }
    });

    deleteProjectBtn.addEventListener('click', deleteCurrentProject);

    // Toolbar
    refreshBtn.addEventListener('click', loadKeys);
    generateKeyBtn.addEventListener('click', () => {
        if (!currentProject) return showToast('请先选择一个项目');
        openKeyModal();
    });

    // Forms
    projectForm.addEventListener('submit', handleProjectSubmit);
    keyForm.addEventListener('submit', handleKeySubmit);
    entitlementForm.addEventListener('submit', handleEntitlementSubmit);
    remarksForm.addEventListener('submit', handleRemarksSubmit);
    authTypeInput.addEventListener('change', updateEntitlementFieldsVisibility);

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
    updateProjectTypeUI();

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
    const projectType = document.getElementById('projectType').value;
    const desc = document.getElementById('projectDescInput').value;

    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/projects/${id}` : '/api/projects';

    try {
        const res = await apiRequest(url, {
            method,
            body: JSON.stringify({
                name,
                description: desc,
                project_type: projectType
            })
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
        keysTableBody.innerHTML = '<tr><td colspan="8" style="text-align:center">Loading...</td></tr>';

        const res = await apiRequest(`/api/keys?project_id=${currentProject.id}`);
        const licenses = await res.json();

        renderKeys(licenses);
        updateStats(licenses);
    } catch (e) {
        console.error(e);
        showToast('加载授权列表失败');
    }
}

function renderKeys(licenses) {
    keysTableBody.innerHTML = '';
    const isPlaybackProject = currentProject?.project_type === 'playback';

    if (licenses.length === 0) {
        emptyState.style.display = 'block';
        return;
    }
    emptyState.style.display = 'none';

    licenses.forEach(license => {
        const tr = document.createElement('tr');
        const createdDate = new Date(license.created_at).toLocaleString();
        const validUntil = license.valid_until || '-';
        const remainingPlays = formatRemainingPlays(license);

        const statusClass = license.is_active ? 'status-active' : 'status-disabled';
        const statusText = license.is_active ? '已激活' : '已禁用';

        tr.innerHTML = `
            <td data-label="密钥"><span class="key-mono">${escapeHtml(license.license_key)}</span></td>
            <td data-label="状态"><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td class="playback-only" data-label="授权方式">${formatAuthType(license.auth_type)}</td>
            <td class="playback-only" data-label="剩余次数">${remainingPlays}</td>
            <td class="playback-only" data-label="到期时间">${escapeHtml(validUntil)}</td>
            <td data-label="备注">${escapeHtml(license.remarks || '-')}</td>
            <td data-label="创建时间">${createdDate}</td>
            <td class="actions-cell" data-label="操作">
               <!-- To be filled by JS for event binding safely -->
            </td>
        `;

        // Actions
        const actionsTd = tr.querySelector('.actions-cell');

        const copyBtn = createBtn('复制', () => {
            navigator.clipboard.writeText(license.license_key);
            showToast('密钥已复制到剪贴板');
        });

        const toggleBtn = createBtn(license.is_active ? '禁用' : '启用', () => toggleKey(license));

        const delBtn = createBtn('删除', () => deleteKey(license), true);

        actionsTd.appendChild(copyBtn);
        actionsTd.appendChild(toggleBtn);
        if (isPlaybackProject) {
            const remarksBtn = createBtn('备注', () => openRemarksModal(license));
            const entitlementBtn = createBtn('权益', () => openEntitlementModal(license));
            const sessionsBtn = createBtn('日志', () => openSessionsModal(license));
            actionsTd.appendChild(remarksBtn);
            actionsTd.appendChild(entitlementBtn);
            actionsTd.appendChild(sessionsBtn);
        }
        actionsTd.appendChild(delBtn);

        keysTableBody.appendChild(tr);
    });
    updateProjectTypeUI();
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatAuthType(authType) {
    const labels = {
        unlimited: '不限',
        count: '按次数',
        date: '按日期',
        count_date: '次数+日期'
    };
    return labels[authType || 'unlimited'] || authType;
}

function formatRemainingPlays(license) {
    if (!['count', 'count_date'].includes(license.auth_type)) {
        return '不限';
    }
    return license.remaining_plays ?? 0;
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

function updateStats(licenses) {
    statsTotal.textContent = licenses.length;
    statsActive.textContent = licenses.filter(l => l.is_active).length;
    // Show disabled count instead
    statsBound.textContent = licenses.filter(l => !l.is_active).length;
}

async function handleKeySubmit(e) {
    e.preventDefault();
    if (!currentProject) return;

    const remarks = document.getElementById('keyRemarks').value;
    const customKey = customKeyInput.value.trim();
    if (currentProject.project_type === 'playback' && !customKey) {
        showToast('请填写播控端生成的机器码');
        return;
    }

    try {
        const res = await apiRequest('/api/keys', {
            method: 'POST',
            body: JSON.stringify({
                project_id: currentProject.id,
                remarks,
                custom_key: customKey
            })
        });

        const data = await res.json();
        if (data.message && !data.success) throw new Error(data.message);

        closeModal(keyModal);
        showToast(data.message || '授权创建成功');
        loadKeys();
        document.getElementById('keyRemarks').value = ''; // Reset
        customKeyInput.value = ''; // Reset
    } catch (e) {
        showToast(e.message || '创建失败');
    }
}

async function deleteKey(license) {
    if (!confirm('确定要删除此授权吗？')) return;

    try {
        const keyValue = encodeURIComponent(license.license_key);
        const res = await apiRequest(`/api/keys/${keyValue}?project_id=${currentProject.id}`, {
            method: 'DELETE' 
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || '授权已删除');
            loadKeys();
        }
    } catch (e) {
        showToast(e.message || '删除授权失败');
    }
}

async function toggleKey(license) {
    try {
        const keyValue = encodeURIComponent(license.license_key);
        const res = await apiRequest(`/api/keys/${keyValue}/status?project_id=${currentProject.id}`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: !license.is_active })
        });

        const data = await res.json();
        if (data.success) {
            showToast(data.message || `授权已${!license.is_active ? '启用' : '禁用'}`);
            loadKeys();
        }
    } catch (e) {
        showToast(e.message || '更新状态失败');
    }
}

// --- Remarks Logic ---

function openRemarksModal(license) {
    document.getElementById('remarksKeyValue').value = license.license_key;
    document.getElementById('remarksKeyDisplay').value = license.license_key;
    document.getElementById('remarksInput').value = license.remarks || '';
    openModal(remarksModal);
}

async function handleRemarksSubmit(e) {
    e.preventDefault();

    const keyValue = document.getElementById('remarksKeyValue').value;
    const remarks = document.getElementById('remarksInput').value;

    try {
        const encodedKey = encodeURIComponent(keyValue);
        const res = await apiRequest(`/api/keys/${encodedKey}/remarks?project_id=${currentProject.id}`, {
            method: 'PUT',
            body: JSON.stringify({ remarks })
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.message || '备注更新失败');

        closeModal(remarksModal);
        showToast('备注已更新');
        loadKeys();
    } catch (e) {
        showToast(e.message || '备注更新失败');
    }
}

// --- Entitlement Logic ---

function openEntitlementModal(license) {
    document.getElementById('entitlementLicenseId').value = license.id;
    document.getElementById('entitlementKeyDisplay').value = license.license_key;
    authTypeInput.value = license.auth_type || 'unlimited';
    document.getElementById('remainingPlaysInput').value = license.remaining_plays ?? '';
    document.getElementById('addPlaysInput').value = '';
    document.getElementById('validUntilInput').value = license.valid_until || '';
    updateEntitlementFieldsVisibility();
    openModal(entitlementModal);
}

function updateEntitlementFieldsVisibility() {
    const authType = authTypeInput.value;
    const showCountFields = authType === 'count' || authType === 'count_date';
    const showDateField = authType === 'date' || authType === 'count_date';

    remainingPlaysGroup.style.display = showCountFields ? '' : 'none';
    addPlaysGroup.style.display = showCountFields ? '' : 'none';
    validUntilGroup.style.display = showDateField ? '' : 'none';
}

async function handleEntitlementSubmit(e) {
    e.preventDefault();

    const licenseId = document.getElementById('entitlementLicenseId').value;
    const authType = document.getElementById('authTypeInput').value;
    const remainingPlays = document.getElementById('remainingPlaysInput').value;
    const addPlays = document.getElementById('addPlaysInput').value;
    const validUntil = document.getElementById('validUntilInput').value;

    try {
        const res = await apiRequest(`/api/licenses/${licenseId}/entitlement`, {
            method: 'PUT',
            body: JSON.stringify({
                auth_type: authType,
                remaining_plays: remainingPlays,
                add_plays: addPlays,
                valid_until: validUntil
            })
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.message || '保存失败');

        closeModal(entitlementModal);
        showToast('授权权益已更新');
        loadKeys();
    } catch (e) {
        showToast(e.message || '保存失败');
    }
}

async function openSessionsModal(license) {
    const sessionsList = document.getElementById('sessionsList');
    sessionsList.textContent = '加载中...';
    openModal(sessionsModal);

    try {
        const res = await apiRequest(`/api/licenses/${license.id}/play-sessions`);
        const sessions = await res.json();
        renderSessions(sessions);
    } catch (e) {
        sessionsList.textContent = e.message || '加载日志失败';
    }
}

function renderSessions(sessions) {
    const sessionsList = document.getElementById('sessionsList');
    sessionsList.innerHTML = '';

    if (!sessions.length) {
        sessionsList.textContent = '暂无播放日志。';
        return;
    }

    const table = document.createElement('table');
    table.className = 'sessions-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th>状态</th>
                <th>开始时间</th>
                <th>结束时间</th>
                <th>时长</th>
                <th>机器码</th>
                <th>客户端版本</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;

    const tbody = table.querySelector('tbody');
    sessions.forEach(session => {
        const tr = document.createElement('tr');
        const startedAt = session.started_at ? new Date(session.started_at).toLocaleString() : '-';
        const endedAt = session.ended_at ? new Date(session.ended_at).toLocaleString() : '-';
        const duration = session.duration_seconds == null ? '-' : `${session.duration_seconds}s`;

        tr.innerHTML = `
            <td>${formatSessionStatus(session.status)}</td>
            <td>${escapeHtml(startedAt)}</td>
            <td>${escapeHtml(endedAt)}</td>
            <td>${escapeHtml(duration)}</td>
            <td><span class="key-mono">${escapeHtml(session.machine_code || '-')}</span></td>
            <td>${escapeHtml(session.client_version || '-')}</td>
        `;
        tbody.appendChild(tr);
    });

    sessionsList.appendChild(table);
}

function formatSessionStatus(status) {
    const labels = {
        playing: '播放中',
        ended: '正常结束',
        timeout: '超时未结束'
    };
    return labels[status] || status;
}

// --- Helpers ---

function updateProjectTypeUI() {
    const type = currentProject?.project_type || 'activation';
    const isPlayback = type === 'playback';
    const docsLink = document.getElementById('docsNavLink');

    document.querySelectorAll('.playback-only').forEach(el => {
        el.style.display = isPlayback ? '' : 'none';
    });

    if (keyHeader) {
        const labels = {
            account: '账号标识',
            activation: '激活码 (Key)',
            playback: '机器码'
        };
        keyHeader.textContent = labels[type] || '密钥 (Key)';
    }

    if (docsLink) {
        docsLink.href = `/docs/${type}`;
        docsLink.textContent = `${projectTypeLabels[type] || '业务'}文档`;
    }

    if (generateKeyBtn) {
        const labels = {
            account: '新增账号授权',
            activation: '生成激活码',
            playback: '新增播控授权'
        };
        generateKeyBtn.textContent = labels[type] || '生成密钥';
    }
}

function openKeyModal() {
    const type = currentProject?.project_type || 'activation';
    const config = {
        account: {
            title: '新增账号授权',
            label: '账号标识',
            placeholder: '例如：手机号、邮箱、账号 ID',
            submit: '创建'
        },
        activation: {
            title: '生成新激活码',
            label: '自定义激活码 (可选)',
            placeholder: '留空则自动生成，支持中文、手机号等',
            submit: '生成'
        },
        playback: {
            title: '新增播控授权',
            label: '客户端机器码',
            placeholder: '请输入播控端生成并显示的机器码',
            submit: '创建'
        }
    }[type];

    keyModalTitle.textContent = config.title;
    customKeyLabel.textContent = config.label;
    customKeyInput.placeholder = config.placeholder;
    customKeyInput.required = type === 'playback';
    keySubmitBtn.textContent = config.submit;
    openModal(keyModal);
}

function openProjectModal(project = null) {
    const title = document.getElementById('projectModalTitle');
    const idInput = document.getElementById('projectId');
    const nameInput = document.getElementById('projectName');
    const typeInput = document.getElementById('projectType');
    const descInput = document.getElementById('projectDescInput');

    if (project) {
        title.textContent = '编辑项目';
        idInput.value = project.id;
        nameInput.value = project.name;
        typeInput.value = project.project_type || 'activation';
        descInput.value = project.description;
    } else {
        title.textContent = '新建项目';
        idInput.value = '';
        nameInput.value = '';
        typeInput.value = 'activation';
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

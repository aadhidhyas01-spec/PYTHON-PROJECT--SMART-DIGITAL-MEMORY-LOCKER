document.addEventListener('DOMContentLoaded', () => {
    // --- Navigation ---
    const navItems = document.querySelectorAll('.nav-item[data-section]');
    const sections = document.querySelectorAll('.section');
    const pageTitle = document.getElementById('page-title');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = item.dataset.section;
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            sections.forEach(s => {
                s.classList.remove('active');
                if (s.id === 'sec-' + target) s.classList.add('active');
            });
            const titles = { dashboard:'Dashboard', add:'Add Record', records:'All Records', files:'File Storage' };
            pageTitle.textContent = titles[target] || 'Dashboard';
            if (target === 'records') loadRecords();
            if (target === 'dashboard') loadDashboard();
            if (target === 'files') loadFiles();
        });
    });

    // --- Set default date ---
    const dateInput = document.getElementById('f-date');
    if (dateInput) dateInput.valueAsDate = new Date();

    // --- Load dashboard on start ---
    loadDashboard();

    // --- Add Record Form ---
    document.getElementById('add-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('f-title').value.trim();
        const category = document.getElementById('f-category').value;
        const value = document.getElementById('f-value').value;
        const date = document.getElementById('f-date').value;
        if (!title || !value || !date) return toast('Please fill all fields', 'error');
        try {
            const res = await fetch('/api/records', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, category, value, date })
            });
            const data = await res.json();
            if (data.success) {
                toast('Record added successfully!', 'success');
                e.target.reset();
                dateInput.valueAsDate = new Date();
                loadDashboard();
            } else {
                toast(data.error || 'Error adding record', 'error');
            }
        } catch (err) { toast('Network error', 'error'); }
    });

    // --- Upload File Form ---
    document.getElementById('upload-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('file-input');
        const category = document.getElementById('file-category').value;
        if (!fileInput.files.length) return toast('Please select a file', 'error');
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('category', category);
        try {
            const res = await fetch('/api/files', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success) {
                toast(data.message, 'success');
                e.target.reset();
                loadFiles();
                loadDashboard();
            } else {
                toast(data.error || 'Upload failed', 'error');
            }
        } catch (err) { toast('Network error', 'error'); }
    });

    // --- Search ---
    let searchTimer;
    document.getElementById('search').addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            const sec = document.querySelector('.section.active');
            if (sec && sec.id === 'sec-records') loadRecords(e.target.value);
        }, 300);
    });
});

// ===== Dashboard =====
let lineChart, doughnutChart;

async function loadDashboard() {
    try {
        const res = await fetch('/api/analysis');
        const d = await res.json();
        document.getElementById('s-total').textContent = d.total_records;
        document.getElementById('s-avg').textContent = d.average;
        document.getElementById('s-perf').textContent = d.performance + '%';
        document.getElementById('s-max').textContent = d.max_val;
        document.getElementById('s-min').textContent = d.min_val;
        document.getElementById('s-files').textContent = d.file_count || 0;

        const banner = document.getElementById('status-banner');
        const statusText = document.getElementById('status-text');
        banner.className = 'status-banner';
        statusText.textContent = 'System Status: ' + d.status;
        if (d.status === 'Good') banner.classList.add('good');
        else if (d.status === 'Warning') banner.classList.add('warning');
        else if (d.status === 'Critical') banner.classList.add('critical');
        else banner.classList.add('good');

        const rRes = await fetch('/api/records');
        const records = await rRes.json();
        renderCharts(records, d.categories || {});
    } catch (err) { console.error(err); }
}

function renderCharts(records, categories) {
    const recent = records.slice(0, 20).reverse();
    const labels = recent.map(r => r.date ? r.date.substring(5) : '');
    const values = recent.map(r => r.value);
    Chart.defaults.color = '#7a829e';
    Chart.defaults.borderColor = '#252d44';

    const lineCtx = document.getElementById('lineChart').getContext('2d');
    if (lineChart) lineChart.destroy();
    lineChart = new Chart(lineCtx, {
        type: 'line',
        data: { labels, datasets: [{ label:'Value', data:values, borderColor:'#4f8cff', backgroundColor:'rgba(79,140,255,0.15)', borderWidth:2, pointRadius:4, pointBackgroundColor:'#0b0f19', pointBorderColor:'#4f8cff', fill:true, tension:0.35 }] },
        options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true}} }
    });

    const catLabels = Object.keys(categories);
    const catValues = Object.values(categories);
    const colors = ['#4f8cff','#34d399','#a78bfa','#fb923c','#f87171','#facc15'];
    const dCtx = document.getElementById('doughnutChart').getContext('2d');
    if (doughnutChart) doughnutChart.destroy();
    doughnutChart = new Chart(dCtx, {
        type: 'doughnut',
        data: { labels: catLabels.length ? catLabels : ['No Data'], datasets:[{ data: catValues.length ? catValues : [1], backgroundColor: catLabels.length ? colors.slice(0,catLabels.length) : ['#252d44'], borderWidth:0 }] },
        options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'bottom',labels:{padding:15,font:{size:12}}}} }
    });
}

// ===== Records Table =====
async function loadRecords(search) {
    try {
        let url = '/api/records';
        if (search) url += '?search=' + encodeURIComponent(search);
        const res = await fetch(url);
        const records = await res.json();
        const tbody = document.getElementById('table-body');
        const noData = document.getElementById('no-data');
        tbody.innerHTML = '';
        if (!records.length) { noData.style.display = 'block'; return; }
        noData.style.display = 'none';
        records.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>#${r.id}</td><td>${r.title}</td><td><span class="badge">${r.category}</span></td><td><strong>${r.value}</strong></td><td>${r.date}</td><td><button class="btn-del" onclick="deleteRecord(${r.id})">🗑 Delete</button></td>`;
            tbody.appendChild(tr);
        });
    } catch (err) { console.error(err); }
}

async function deleteRecord(id) {
    if (!confirm('Delete this record?')) return;
    try {
        const res = await fetch('/api/records/' + id, { method:'DELETE' });
        const data = await res.json();
        if (data.success) { toast('Record deleted','success'); loadRecords(); loadDashboard(); }
    } catch (err) { toast('Error deleting','error'); }
}

// ===== Files =====
function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
    return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

async function loadFiles() {
    try {
        const res = await fetch('/api/files');
        const files = await res.json();
        const tbody = document.getElementById('files-body');
        const noFiles = document.getElementById('no-files');
        tbody.innerHTML = '';
        if (!files.length) { noFiles.style.display = 'block'; return; }
        noFiles.style.display = 'none';
        files.forEach(f => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${f.id}</td>
                <td>${f.original_name}</td>
                <td><span class="badge">${f.file_type.toUpperCase()}</span></td>
                <td>${formatSize(f.file_size)}</td>
                <td><span class="badge">${f.category}</span></td>
                <td>${f.uploaded_at ? f.uploaded_at.substring(0,10) : ''}</td>
                <td>
                    <a href="/api/files/${f.id}/download" class="btn-dl">⬇ Download</a>
                    <button class="btn-del" onclick="deleteFile(${f.id})">🗑 Delete</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) { console.error(err); }
}

async function deleteFile(id) {
    if (!confirm('Delete this file permanently?')) return;
    try {
        const res = await fetch('/api/files/' + id, { method:'DELETE' });
        const data = await res.json();
        if (data.success) { toast('File deleted','success'); loadFiles(); loadDashboard(); }
    } catch (err) { toast('Error deleting file','error'); }
}

// ===== Toast =====
function toast(msg, type) {
    const container = document.getElementById('toasts');
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity='0'; setTimeout(() => el.remove(), 300); }, 3000);
}

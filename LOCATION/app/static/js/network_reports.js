(async () => {
    const token = sessionStorage.getItem('token') || await window.DomainSSO.attempt();
    if (!token) { location.replace('/?return_to=' + encodeURIComponent(location.pathname)); return; }
    const headers = {Authorization: `Bearer ${token}`};
    const message = document.getElementById('message');
    let report = null;
    async function request(url) {
        const response = await window.ApiClient.request(url, {headers});
        if (!response.ok) throw new Error(response.status === 403 ? 'Доступ запрещён' : `Ошибка загрузки (${response.status})`);
        return response;
    }
    function render() {
        const body = document.getElementById('rows'); body.replaceChildren();
        const query = document.getElementById('search').value.trim().toLocaleLowerCase();
        const items = report.items.filter(row => Object.values(row).join(' ').toLocaleLowerCase().includes(query));
        for (const row of items) {
            const tr = document.createElement('tr');
            for (const key of Object.keys(report.columns)) {
                const td = document.createElement('td'); td.textContent = row[key] ?? ''; tr.append(td);
            }
            body.append(tr);
        }
        message.textContent = `Строк: ${items.length} из ${report.total}`;
    }
    function endpoint(suffix = '') {
        const branch = document.getElementById('branch').value;
        return '/api/v1/location/reports' + suffix + (branch ? '?branch_id=' + encodeURIComponent(branch) : '');
    }
    async function load() {
        try {
            message.textContent = 'Формирование…';
            report = await (await request(endpoint())).json();
            const tr = document.createElement('tr');
            for (const label of Object.values(report.columns)) { const th = document.createElement('th'); th.textContent = label; tr.append(th); }
            document.getElementById('head').replaceChildren(tr); render();
        } catch (error) { message.textContent = error.message; }
    }
    try {
        const user = await (await request('/api/v1/auth/me')).json();
        if (user.must_change_password) { location.replace('/'); return; }
        if (user.role === 'operator') document.getElementById('map').remove();
        const branches = await (await request('/api/branches')).json();
        const select = document.getElementById('branch');
        if (user.role === 'superadmin') select.add(new Option('Все филиалы', ''));
        for (const branch of branches) select.add(new Option(branch.name, branch.id));
        if (user.branch_id) select.value = String(user.branch_id);
        select.onchange = load;
        document.getElementById('refresh').onclick = load;
        document.getElementById('search').oninput = () => { if (report) render(); };
        document.getElementById('export').onclick = async () => {
            try {
                const blob = await (await request(endpoint('/csv'))).blob();
                const url = URL.createObjectURL(blob), a = document.createElement('a');
                a.href = url; a.download = 'network-report.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
            } catch (error) { message.textContent = error.message; }
        };
        await load();
    } catch (error) { message.textContent = error.message; }
})();

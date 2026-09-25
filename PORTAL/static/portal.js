document.addEventListener('alpine:init', () => {
    Alpine.data('portalApp', () => ({
        token: localStorage.getItem('token') || '',
        currentUser: null,
        branches: [],
        selectedBranchId: '',
        
        // Статистика модулей
        cartridgeStats: { total: 0, in_use: 0, pending: 0, at_vendor: 0, ready: 0 },
        repairStats: { total: 0, working: 0, broken: 0, in_sc: 0, returned: 0 },
        locationStats: { floors: 0, zones: 0, assets_placed: 0, switches: 0 },

        // Форма входа
        showLoginModal: false,
        loginForm: {
            username: '',
            password: '',
            auth_type: 'local' // 'local' | 'ad'
        },
        loginError: '',
        loginLoading: false,

        // Настройки и филиалы
        showSettingsModal: false,
        settingsData: {},
        isSyncingAD: false,
        isTestingLDAP: false,
        showBindPwd: false,
        ldapTestResult: { success: false, message: '' },

        // Управление пользователями
        showUsersModal: false,
        usersList: [],
        isLoadingUsers: false,
        showUserEditModal: false,
        isEditingUser: false,
        userForm: { id: null, username: '', full_name: '', password: '', auth_type: 'local', role: 'operator', branch_id: '', is_active: true },

        // Управление филиалами и этажами
        showBranchesModal: false,
        managingBranchId: null,
        branchFloors: [],
        isLoadingFloors: false,
        showBranchEditModal: false,
        isEditingBranch: false,
        branchForm: { id: null, name: '', code: '', address: '', it_office: '', notes: '' },
        showFloorEditModal: false,
        isEditingFloor: false,
        floorForm: { id: null, branch_id: null, floor_number: 1, name: '', scale_pixels_per_meter: 20.0 },

        toast: { show: false, message: '', type: 'info' },

        showToast(msg, type = 'info') {
            this.toast.message = msg;
            this.toast.type = type;
            this.toast.show = true;
            setTimeout(() => { this.toast.show = false; }, 3500);
        },

        async init() {
            if (!this.token) {
                this.showLoginModal = true;
                return;
            }

            const ok = await this.loadCurrentUser();
            if (!ok) {
                this.showLoginModal = true;
                return;
            }

            await this.loadBranches();
            await this.loadPortalStats();
        },

        getAuthHeaders() {
            return {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            };
        },

        async loadCurrentUser() {
            try {
                const res = await fetch('/api/v1/auth/me', { headers: this.getAuthHeaders() });
                if (!res.ok) {
                    localStorage.removeItem('token');
                    this.token = '';
                    return false;
                }
                this.currentUser = await res.json();
                if (this.currentUser.branch_id) {
                    this.selectedBranchId = this.currentUser.branch_id;
                }
                return true;
            } catch (e) {
                localStorage.removeItem('token');
                this.token = '';
                return false;
            }
        },

        async loadBranches() {
            try {
                const res = await fetch('/api/branches', { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.branches = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        },

        async loadPortalStats() {
            try {
                // Загружаем статистику для картриджей
                const cartRes = await fetch('/api/reports/data?report_type=all' + (this.selectedBranchId ? '&branch_id=' + this.selectedBranchId : ''), { headers: this.getAuthHeaders() });
                if (cartRes.ok) {
                    const cData = await cartRes.json();
                    if (cData.report && cData.report.summary) {
                        const s = cData.report.summary;
                        this.cartridgeStats = {
                            total: s.total || 0,
                            in_use: s.in_use || 0,
                            pending: s.pending_vendor || 0,
                            at_vendor: s.at_vendor || 0,
                            ready: s.ready_for_pickup || 0
                        };
                    }
                }

                // Загружаем статистику ремонта
                const repRes = await fetch('/api/v1/repair/reports/data' + (this.selectedBranchId ? '?branch_id=' + this.selectedBranchId : ''), { headers: this.getAuthHeaders() });
                if (repRes.ok) {
                    const rData = await repRes.json();
                    if (rData.report && rData.report.summary) {
                        const s = rData.report.summary;
                        this.repairStats = {
                            total: s.total_count || 0,
                            working: s.working_count || 0,
                            broken: s.broken_count || 0,
                            in_sc: (s.pending_sc || 0) + (s.at_sc || 0),
                            returned: s.returned_it || 0
                        };
                    }
                }

                // Загружаем статистику локаций
                const locRes = await fetch('/api/v1/location/stats' + (this.selectedBranchId ? '?branch_id=' + this.selectedBranchId : ''), { headers: this.getAuthHeaders() });
                if (locRes.ok) {
                    this.locationStats = await locRes.json();
                }
            } catch (e) {
                console.error('Stats loading warning', e);
            }
        },

        async submitLogin() {
            this.loginLoading = true;
            this.loginError = '';
            try {
                const res = await fetch('/api/v1/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: this.loginForm.username.trim(),
                        password: this.loginForm.password,
                        auth_type: this.loginForm.auth_type
                    })
                });
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.detail || 'Неверный логин или пароль');
                }
                this.token = data.access_token;
                localStorage.setItem('token', this.token);
                this.showLoginModal = false;
                await this.loadCurrentUser();
                await this.loadBranches();
                await this.loadPortalStats();
                this.showToast('Вход выполнен успешно!', 'success');
            } catch (e) {
                this.loginError = e.message;
            } finally {
                this.loginLoading = false;
            }
        },

        logout() {
            localStorage.removeItem('token');
            this.token = '';
            this.currentUser = null;
            this.showLoginModal = true;
        },

        openModule(path) {
            // Переход в модуль с передачей токена в URL для мгновенной сессии
            window.location.href = `${path}?token=${encodeURIComponent(this.token)}`;
        },

        async openSettings() {
            try {
                const res = await fetch('/api/settings', { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.settingsData = await res.json();
                    this.ldapTestResult = { success: false, message: '' };
                    this.showSettingsModal = true;
                }
            } catch (e) {
                this.showToast('Ошибка загрузки настроек', 'error');
            }
        },

        normalizeLdapHost(host) {
            if (!host) return host;
            let h = host.trim();
            // Исправляем популярную опечатку слитного порта: e.g. dc01.gp1.loc389 -> dc01.gp1.loc:389
            const match = h.match(/^(.*?[a-zA-Z\-_])(389|636|3268|3269)$/);
            if (match) {
                h = `${match[1]}:${match[2]}`;
            }
            return h;
        },

        onLdapHostBlur() {
            if (this.settingsData.ad_host) {
                this.settingsData.ad_host = this.normalizeLdapHost(this.settingsData.ad_host);
            }
        },

        async testLdapConnection() {
            if (this.settingsData.ad_host) {
                this.settingsData.ad_host = this.normalizeLdapHost(this.settingsData.ad_host);
            }
            this.isTestingLDAP = true;
            this.ldapTestResult = { success: false, message: '' };
            try {
                const res = await fetch('/api/settings/ldap/test', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({
                        host: this.settingsData.ad_host,
                        base_dn: this.settingsData.ad_base_dn,
                        bind_user: this.settingsData.ad_bind_user,
                        bind_password: this.settingsData.ad_bind_password
                    })
                });
                const data = await res.json();
                const displayMsg = data.detail || data.message || (data.success ? 'Подключение успешно установлено!' : 'Ошибка подключения к AD');
                this.ldapTestResult = {
                    success: !!data.success,
                    message: displayMsg
                };
                if (data.success) {
                    this.showToast(displayMsg, 'success');
                } else {
                    this.showToast(displayMsg, 'error');
                }
            } catch (e) {
                this.ldapTestResult = {
                    success: false,
                    message: 'Сетевая ошибка при проверке: ' + e.message
                };
                this.showToast('Ошибка запроса проверки AD: ' + e.message, 'error');
            } finally {
                this.isTestingLDAP = false;
            }
        },

        async saveSettings() {
            if (this.settingsData.ad_host) {
                this.settingsData.ad_host = this.normalizeLdapHost(this.settingsData.ad_host);
            }
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ settings: this.settingsData })
                });
                if (res.ok) {
                    this.showToast('Настройки успешно сохранены', 'success');
                    this.showSettingsModal = false;
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка сохранения настроек', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка сохранения настроек', 'error');
            }
        },

        async syncADUsers() {
            this.isSyncingAD = true;
            try {
                const res = await fetch('/api/settings/ldap/sync', {
                    method: 'POST',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok && (data.success || data.status === 'success')) {
                    this.showToast(data.message || 'Сотрудники из AD успешно синхронизированы', 'success');
                } else {
                    this.showToast(data.message || 'Ошибка синхронизации AD', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка обращения к Active Directory', 'error');
            } finally {
                this.isSyncingAD = false;
            }
        },

        // ==========================================
        // УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
        // ==========================================
        async openUsersModal() {
            this.showUsersModal = true;
            await this.loadUsers();
        },

        async loadUsers() {
            this.isLoadingUsers = true;
            try {
                const res = await fetch('/api/app-users', { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.usersList = await res.json();
                } else {
                    this.showToast('Не удалось загрузить список пользователей', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка при загрузке пользователей', 'error');
            } finally {
                this.isLoadingUsers = false;
            }
        },

        openCreateUser() {
            this.isEditingUser = false;
            this.userForm = {
                id: null,
                username: '',
                full_name: '',
                password: '',
                auth_type: 'local',
                role: 'operator',
                branch_id: this.branches.length ? this.branches[0].id : '',
                is_active: true
            };
            this.showUserEditModal = true;
        },

        openEditUser(u) {
            this.isEditingUser = true;
            this.userForm = {
                id: u.id,
                username: u.username,
                full_name: u.full_name,
                password: '',
                auth_type: u.auth_type,
                role: u.role,
                branch_id: u.branch_id || '',
                is_active: u.is_active
            };
            this.showUserEditModal = true;
        },

        async saveUser() {
            try {
                const payload = {
                    username: this.userForm.username.trim(),
                    full_name: this.userForm.full_name.trim(),
                    role: this.userForm.role,
                    auth_type: this.userForm.auth_type,
                    branch_id: this.userForm.branch_id ? parseInt(this.userForm.branch_id) : null,
                    is_active: this.userForm.is_active
                };

                let res;
                if (this.isEditingUser) {
                    if (this.userForm.password) {
                        payload.password = this.userForm.password;
                    }
                    res = await fetch(`/api/app-users/${this.userForm.id}`, {
                        method: 'PUT',
                        headers: this.getAuthHeaders(),
                        body: JSON.stringify(payload)
                    });
                } else {
                    payload.password = this.userForm.password;
                    res = await fetch('/api/app-users', {
                        method: 'POST',
                        headers: this.getAuthHeaders(),
                        body: JSON.stringify(payload)
                    });
                }

                if (res.ok) {
                    this.showToast(this.isEditingUser ? 'Пользователь обновлен' : 'Пользователь успешно создан', 'success');
                    this.showUserEditModal = false;
                    await this.loadUsers();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка сохранения пользователя', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка сохранения: ' + e.message, 'error');
            }
        },

        async toggleUserActive(u) {
            try {
                const res = await fetch(`/api/app-users/${u.id}/toggle-active`, {
                    method: 'POST',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast(data.message, 'success');
                    await this.loadUsers();
                } else {
                    this.showToast(data.detail || 'Ошибка изменения статуса', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка', 'error');
            }
        },

        async deleteUser(u) {
            if (!confirm(`Вы действительно хотите удалить пользователя "${u.username}" (${u.full_name})?`)) {
                return;
            }
            try {
                const res = await fetch(`/api/app-users/${u.id}`, {
                    method: 'DELETE',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast(data.message || 'Пользователь удален', 'success');
                    await this.loadUsers();
                } else {
                    this.showToast(data.detail || 'Не удалось удалить пользователя', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка удаления', 'error');
            }
        },

        // ==========================================
        // УПРАВЛЕНИЕ ФИЛИАЛАМИ И ЭТАЖАМИ
        // ==========================================
        async openBranchesModal() {
            this.showBranchesModal = true;
            await this.loadBranches();
            if (this.branches.length && !this.managingBranchId) {
                await this.selectBranch(this.branches[0].id);
            } else if (this.managingBranchId) {
                await this.selectBranch(this.managingBranchId);
            }
        },

        async selectBranch(branchId) {
            this.managingBranchId = branchId;
            this.isLoadingFloors = true;
            try {
                const res = await fetch(`/api/v1/location/branches/${branchId}/floors`, {
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    this.branchFloors = await res.json();
                } else {
                    this.branchFloors = [];
                }
            } catch (e) {
                console.error(e);
                this.branchFloors = [];
            } finally {
                this.isLoadingFloors = false;
            }
        },

        openCreateBranch() {
            this.isEditingBranch = false;
            this.branchForm = { id: null, name: '', code: '', address: '', it_office: '', notes: '' };
            this.showBranchEditModal = true;
        },

        openEditBranch(b) {
            this.isEditingBranch = true;
            this.branchForm = {
                id: b.id,
                name: b.name,
                code: b.code || '',
                address: b.address || '',
                it_office: b.it_office || '',
                notes: b.notes || ''
            };
            this.showBranchEditModal = true;
        },

        async saveBranch() {
            try {
                const payload = {
                    name: this.branchForm.name.trim(),
                    code: this.branchForm.code.trim() || null,
                    address: this.branchForm.address.trim() || null,
                    it_office: this.branchForm.it_office.trim() || null,
                    notes: this.branchForm.notes.trim() || null
                };

                let res;
                if (this.isEditingBranch) {
                    res = await fetch(`/api/branches/${this.branchForm.id}`, {
                        method: 'PUT',
                        headers: this.getAuthHeaders(),
                        body: JSON.stringify(payload)
                    });
                } else {
                    res = await fetch('/api/branches', {
                        method: 'POST',
                        headers: this.getAuthHeaders(),
                        body: JSON.stringify(payload)
                    });
                }

                if (res.ok) {
                    this.showToast(this.isEditingBranch ? 'Филиал обновлен' : 'Филиал создан', 'success');
                    this.showBranchEditModal = false;
                    await this.loadBranches();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка сохранения филиала', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка сохранения филиала', 'error');
            }
        },

        async deleteBranch(b) {
            if (!confirm(`Удалить филиал "${b.name}"?`)) return;
            try {
                const res = await fetch(`/api/branches/${b.id}`, {
                    method: 'DELETE',
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    this.showToast('Филиал удален', 'success');
                    await this.loadBranches();
                    if (this.branches.length) {
                        await this.selectBranch(this.branches[0].id);
                    } else {
                        this.branchFloors = [];
                    }
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Не удалось удалить филиал', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка удаления', 'error');
            }
        },

        openCreateFloor() {
            if (!this.managingBranchId) {
                this.showToast('Сначала выберите филиал', 'info');
                return;
            }
            this.isEditingFloor = false;
            this.floorForm = {
                id: null,
                branch_id: this.managingBranchId,
                floor_number: this.branchFloors.length + 1,
                name: `${this.branchFloors.length + 1}-й Этаж`,
                scale_pixels_per_meter: 20.0
            };
            this.showFloorEditModal = true;
        },

        openEditFloor(f) {
            this.isEditingFloor = true;
            this.floorForm = {
                id: f.id,
                branch_id: f.branch_id,
                floor_number: f.floor_number,
                name: f.name,
                scale_pixels_per_meter: f.scale_pixels_per_meter || 20.0
            };
            this.showFloorEditModal = true;
        },

        async saveFloor() {
            try {
                let res;
                if (this.isEditingFloor) {
                    res = await fetch(`/api/v1/location/floors/${this.floorForm.id}`, {
                        method: 'PUT',
                        headers: this.getAuthHeaders(),
                        body: JSON.stringify({
                            name: this.floorForm.name.trim(),
                            floor_number: parseInt(this.floorForm.floor_number),
                            scale_pixels_per_meter: parseFloat(this.floorForm.scale_pixels_per_meter)
                        })
                    });
                } else {
                    res = await fetch('/api/v1/location/floors', {
                        method: 'POST',
                        headers: this.getAuthHeaders(),
                        body: JSON.stringify({
                            branch_id: this.managingBranchId,
                            floor_number: parseInt(this.floorForm.floor_number),
                            name: this.floorForm.name.trim(),
                            scale_pixels_per_meter: parseFloat(this.floorForm.scale_pixels_per_meter)
                        })
                    });
                }

                if (res.ok) {
                    this.showToast(this.isEditingFloor ? 'Этаж обновлен' : 'Этаж успешно добавлен', 'success');
                    this.showFloorEditModal = false;
                    await this.selectBranch(this.managingBranchId);
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка сохранения этажа', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка сохранения этажа', 'error');
            }
        },

        async deleteFloor(f) {
            if (!confirm(`Удалить этаж "${f.name}" и все связанные зоны?`)) return;
            try {
                const res = await fetch(`/api/v1/location/floors/${f.id}`, {
                    method: 'DELETE',
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    this.showToast('Этаж удален', 'success');
                    await this.selectBranch(this.managingBranchId);
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Не удалось удалить этаж', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка удаления этажа', 'error');
            }
        },

        async uploadFloorMapFile(floorId, event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch(`/api/v1/location/floors/${floorId}/upload-map`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${this.token}` },
                    body: formData
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast('План этажа успешно загружен!', 'success');
                    await this.selectBranch(this.managingBranchId);
                } else {
                    this.showToast(data.detail || 'Ошибка загрузки карты', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка при загрузке карты', 'error');
            } finally {
                event.target.value = '';
            }
        }
    }));
});

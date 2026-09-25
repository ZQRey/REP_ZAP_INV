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

        async testLdapConnection() {
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
                this.ldapTestResult = {
                    success: !!data.success,
                    message: data.message || (data.success ? 'Подключение успешно установлено!' : 'Ошибка подключения к AD')
                };
                if (data.success) {
                    this.showToast(data.message || 'Подключение к AD успешно!', 'success');
                } else {
                    this.showToast(data.message || 'Ошибка подключения к AD', 'error');
                }
            } catch (e) {
                this.ldapTestResult = {
                    success: false,
                    message: 'Сетевая ошибка при проверке: ' + e.message
                };
                this.showToast('Ошибка запроса проверки AD', 'error');
            } finally {
                this.isTestingLDAP = false;
            }
        },

        async saveSettings() {
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
        }
    }));
});

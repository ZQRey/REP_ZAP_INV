document.addEventListener('alpine:init', () => {
    Alpine.data('repairApp', () => ({
        // Аутентификация и контекст
        token: localStorage.getItem('token') || '',
        currentUser: null,
        branches: [],
        selectedBranchId: '',
        adUsers: [],
        
        // Текущая вкладка
        currentTab: 'all', // all, accept, send_sc, return_sc, install_wp, models, reports

        // Списки техники
        equipmentList: [],
        modelsList: [],
        batchesList: [],

        // Фильтры
        searchQuery: '',
        filterType: '',
        filterCondition: '',
        filterStatus: '',

        // Загрузки и фильтрация в приемке
        isLoading: false,
        isAdSyncing: false,
        isSearchingInv: false,
        acceptSuggestions: [],
        showAcceptEqDropdown: false,
        acceptEqNotFound: false,
        acceptIsNewAsset: false,
        eqSearchTimeout: null,

        // Живой фильтр сотрудников AD в приемке
        acceptUserSearch: '',
        acceptUserResults: [],
        showAcceptUserDropdown: false,
        userSearchTimeout: null,

        // Модальные окна
        showAddModal: false,
        showDetailModal: false,
        showReturnModal: false,
        showInstallModal: false,
        showAdSyncModal: false,
        selectedEquipment: null,

        // Форма приемки (Этап 1)
        acceptForm: {
            inventory_number: '',
            serial_number: '',
            name: '',
            asset_type: 'workstation',
            cabinet: '',
            branch_id: '',
            current_user_id: '',
            reported_issue: 'Не включается / неисправность',
            condition: 'broken',
            notes: ''
        },

        // Форма ручного добавления
        addForm: {
            inventory_number: '',
            serial_number: '',
            name: '',
            asset_type: 'workstation',
            condition: 'working',
            status: 'at_workplace',
            cabinet: '',
            branch_id: '',
            current_user_id: '',
            notes: ''
        },

        // Сетевые коммутаторы (Switch Settings)
        isTestingSwitch: false,
        switchTestResult: null,
        addSwitchConfig: {
            ip_address: '',
            management_type: 'omada',
            management_port: 8043,
            username: 'admin',
            password: '',
            snmp_community: 'public',
            total_ports: 24
        },
        editSwitchConfig: {
            ip_address: '',
            management_type: 'omada',
            management_port: 8043,
            username: 'admin',
            password: '',
            snmp_community: 'public',
            total_ports: 24
        },

        // Редактирование техники
        showEditModal: false,
        editForm: {
            id: null,
            inventory_number: '',
            serial_number: '',
            name: '',
            asset_type: 'workstation',
            condition: 'working',
            status: 'at_workplace',
            cabinet: '',
            branch_id: '',
            current_user_id: '',
            notes: ''
        },

        // Справочник моделей
        isSyncingModels: false,
        showModelModal: false,
        modelSearchQuery: '',
        modelCategoryFilter: '',
        modelForm: {
            id: null,
            name: '',
            category: 'workstation',
            vendor: '',
            specs_template: '',
            notes: ''
        },

        // Отправка в СЦ (Этап 2)
        selectedForSC: [],
        scVendorName: 'ООО «ТехноРемСервис»',
        scBatchNotes: '',

        // Принятие из СЦ (Этап 3)
        returnTargetItem: null,
        returnForm: {
            diagnostic_result: 'Ремонт выполнен успешно',
            work_performed: 'Замена неисправных компонентов',
            cost: 0,
            condition: 'working',
            notes: ''
        },

        // Установка на рабочее место (Этап 4)
        installTargetItem: null,
        installForm: {
            cabinet: '',
            current_user_id: '',
            notes: ''
        },

        // Отчеты
        reportFilterCondition: '',
        reportFilterType: '',
        reportSearch: '',
        reportData: null,

        // Уведомления Toast
        toast: {
            show: false,
            message: '',
            type: 'info'
        },

        showToast(message, type = 'info') {
            this.toast.message = message;
            this.toast.type = type;
            this.toast.show = true;
            setTimeout(() => { this.toast.show = false; }, 3500);
        },

        async init() {
            // Если токена нет, проверим URL-параметры или перенаправим на Portal
            const urlParams = new URLSearchParams(window.location.search);
            const tokenParam = urlParams.get('token');
            if (tokenParam) {
                this.token = tokenParam;
                localStorage.setItem('token', tokenParam);
                window.history.replaceState({}, document.title, window.location.pathname);
            }

            if (!this.token) {
                // Переадресация на общий портал
                window.location.href = '/?return_to=' + encodeURIComponent(window.location.pathname);
                return;
            }

            await this.loadCurrentUser();
            await this.loadBranches();
            await this.loadADUsers();
            await this.loadEquipment();
            await this.loadModels();
            await this.loadBatches();
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
                    if (res.status === 401) {
                        localStorage.removeItem('token');
                        window.location.href = '/';
                    }
                    return;
                }
                this.currentUser = await res.json();
                if (this.currentUser.branch_id) {
                    this.selectedBranchId = this.currentUser.branch_id;
                }
            } catch (e) {
                console.error('Failed to load user', e);
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

        async loadADUsers() {
            try {
                let res = await fetch('/api/users?limit=1000', { headers: this.getAuthHeaders() });
                if (!res.ok) {
                    res = await fetch('/api/users/ad?limit=1000', { headers: this.getAuthHeaders() });
                }
                if (!res.ok) {
                    res = await fetch('/api/v1/repair/equipment/ad-users?limit=1000', { headers: this.getAuthHeaders() });
                }
                if (res.ok) {
                    this.adUsers = await res.json();
                }
            } catch (e) {
                console.error("Ошибка загрузки пользователей AD:", e);
            }
        },

        async loadEquipment() {
            this.isLoading = true;
            try {
                let url = `/api/v1/repair/equipment?`;
                if (this.selectedBranchId) url += `branch_id=${this.selectedBranchId}&`;
                if (this.filterCondition) url += `condition_filter=${this.filterCondition}&`;
                if (this.filterStatus) url += `status_filter=${this.filterStatus}&`;
                if (this.filterType) url += `type_filter=${this.filterType}&`;
                if (this.searchQuery) url += `search=${encodeURIComponent(this.searchQuery)}&`;

                const res = await fetch(url, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.equipmentList = await res.json();
                }
            } catch (e) {
                this.showToast('Ошибка загрузки реестра техники', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        async loadModels() {
            try {
                const res = await fetch('/api/v1/repair/models', { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.modelsList = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        },

        async loadBatches() {
            try {
                let url = '/api/v1/repair/batches';
                if (this.selectedBranchId) url += `?branch_id=${this.selectedBranchId}`;
                const res = await fetch(url, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.batchesList = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        },

        // Живой ввод инвентарного номера / имени ПК
        onAcceptInvInput() {
            clearTimeout(this.eqSearchTimeout);
            const q = (this.acceptForm.inventory_number || '').trim();
            if (q.length < 2) {
                this.acceptSuggestions = [];
                this.showAcceptEqDropdown = false;
                this.acceptEqNotFound = false;
                return;
            }
            this.eqSearchTimeout = setTimeout(() => {
                this.filterEquipmentForAccept(q);
            }, 300);
        },

        // Поиск оборудования для фильтра в приемке
        async filterEquipmentForAccept(query) {
            const q = (query || this.acceptForm.inventory_number || '').trim();
            if (!q || q.length < 2) return;
            this.isSearchingInv = true;
            try {
                const res = await fetch(`/api/v1/repair/equipment/find-by-inv?query_str=${encodeURIComponent(q)}`, {
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.found) {
                        this.acceptSuggestions = (data.suggestions && data.suggestions.length > 0)
                            ? data.suggestions
                            : (data.equipment ? [data.equipment] : []);
                        this.acceptEqNotFound = false;
                    } else {
                        this.acceptSuggestions = [];
                        this.acceptEqNotFound = true;
                    }
                    this.showAcceptEqDropdown = true;
                }
            } catch (e) {
                console.error("Ошибка поиска оборудования:", e);
            } finally {
                this.isSearchingInv = false;
            }
        },

        // Переход в режим добавления нового устройства
        startNewAssetAccept() {
            this.showAcceptEqDropdown = false;
            this.acceptIsNewAsset = true;
            this.acceptSuggestions = [];
            this.acceptEqNotFound = false;
            this.$nextTick(() => {
                const el = document.getElementById('accept-model-name');
                if (el) el.focus();
            });
            this.showToast(`Устройство «${this.acceptForm.inventory_number}» будет добавлено в базу при приемке`, 'info');
        },

        // Выбор предложенного совпадения из AD/реестра при поиске
        selectAcceptSuggestion(eq) {
            this.acceptForm.inventory_number = eq.inventory_number;
            this.acceptForm.name = eq.name;
            this.acceptForm.serial_number = eq.serial_number || '';
            this.acceptForm.asset_type = eq.asset_type;
            this.acceptForm.cabinet = eq.cabinet || '';
            if (eq.branch_id) this.acceptForm.branch_id = eq.branch_id;
            if (eq.current_user_id) {
                this.acceptForm.current_user_id = eq.current_user_id;
                const uObj = this.adUsers.find(u => u.samaccountname === eq.current_user_id);
                const uDisp = eq.current_user_name || (uObj ? uObj.display_name : eq.current_user_id);
                this.acceptUserSearch = uDisp + (eq.cabinet ? ` [каб. ${eq.cabinet}]` : '');
                if (!this.adUsers.some(u => u.samaccountname === eq.current_user_id)) {
                    this.adUsers.unshift({
                        samaccountname: eq.current_user_id,
                        display_name: uDisp,
                        cabinet: eq.cabinet || ''
                    });
                }
            } else {
                this.acceptForm.current_user_id = '';
                this.acceptUserSearch = '';
            }
            this.acceptSuggestions = [];
            this.showAcceptEqDropdown = false;
            this.acceptEqNotFound = false;
            this.acceptIsNewAsset = false;
            const label = eq.hostname ? `${eq.hostname} (${eq.inventory_number})` : eq.inventory_number;
            this.showToast(`Выбрано оборудование: ${label}`, 'success');
        },

        // Поиск по кнопке "Найти" или Enter
        async searchInvForAccept() {
            const inv = this.acceptForm.inventory_number ? this.acceptForm.inventory_number.trim() : '';
            if (!inv) return;
            this.isSearchingInv = true;
            try {
                const res = await fetch(`/api/v1/repair/equipment/find-by-inv?query_str=${encodeURIComponent(inv)}`, {
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.found && data.equipment) {
                        this.selectAcceptSuggestion(data.equipment);
                        if (data.suggestions && data.suggestions.length > 1) {
                            this.acceptSuggestions = data.suggestions;
                            this.showAcceptEqDropdown = true;
                        }
                    } else {
                        this.acceptSuggestions = [];
                        this.acceptEqNotFound = true;
                        this.showAcceptEqDropdown = true;
                        this.showToast(`Оборудование "${inv}" не найдено в базе. Нажмите "Добавить", чтобы внести его в реестр.`, 'warning');
                    }
                } else {
                    this.showToast('Ошибка при поиске оборудования', 'error');
                }
            } catch (e) {
                console.error(e);
                this.showToast('Ошибка сетевого запроса при поиске', 'error');
            } finally {
                this.isSearchingInv = false;
            }
        },

        // Живой фильтр сотрудников AD по ФИО / логину / кабинету
        filterAdUsersForAccept() {
            const q = (this.acceptUserSearch || '').trim().toLowerCase();
            if (!q) {
                this.acceptUserResults = this.adUsers.slice(0, 20);
                return;
            }
            const tokens = q.split(/\s+/).filter(Boolean);
            const matches = this.adUsers.filter(u => {
                const name = (u.display_name || '').toLowerCase();
                const sam = (u.samaccountname || '').toLowerCase();
                const cab = (u.cabinet || '').toLowerCase();
                const dep = (u.department || '').toLowerCase();
                const fullText = `${name} ${sam} ${cab} ${dep}`;
                return tokens.every(tok => fullText.includes(tok));
            });

            matches.sort((a, b) => {
                const aName = (a.display_name || '').toLowerCase();
                const bName = (b.display_name || '').toLowerCase();
                const aStarts = aName.startsWith(q) || (a.samaccountname || '').toLowerCase().startsWith(q);
                const bStarts = bName.startsWith(q) || (b.samaccountname || '').toLowerCase().startsWith(q);
                if (aStarts && !bStarts) return -1;
                if (!aStarts && bStarts) return 1;
                return aName.localeCompare(bName);
            });

            this.acceptUserResults = matches.slice(0, 25);

            // Если в кэше мало результатов и длина >= 2, фоновый серверный поиск
            if (this.acceptUserResults.length === 0 && q.length >= 2) {
                clearTimeout(this.userSearchTimeout);
                this.userSearchTimeout = setTimeout(async () => {
                    try {
                        const res = await fetch(`/api/users?q=${encodeURIComponent(q)}&limit=25`, {
                            headers: this.getAuthHeaders()
                        });
                        if (res.ok) {
                            const data = await res.json();
                            if (data && data.length > 0) {
                                data.forEach(u => {
                                    if (!this.adUsers.some(x => x.samaccountname === u.samaccountname)) {
                                        this.adUsers.push(u);
                                    }
                                });
                                this.acceptUserResults = data;
                            }
                        }
                    } catch (e) {
                        console.error("Ошибка серверного поиска сотрудников:", e);
                    }
                }, 250);
            }
        },

        // Выбор сотрудника AD в форме приемки
        selectAcceptUser(u) {
            if (!u) {
                this.acceptForm.current_user_id = '';
                this.acceptUserSearch = '';
                this.showAcceptUserDropdown = false;
                return;
            }
            this.acceptForm.current_user_id = u.samaccountname;
            this.acceptUserSearch = u.display_name + (u.cabinet ? ` [каб. ${u.cabinet}]` : '');
            if (u.cabinet && !this.acceptForm.cabinet) {
                this.acceptForm.cabinet = u.cabinet;
            }
            this.showAcceptUserDropdown = false;
        },

        // Очистка выбора сотрудника AD
        clearAcceptUser() {
            this.acceptForm.current_user_id = '';
            this.acceptUserSearch = '';
            this.showAcceptUserDropdown = false;
        },

        // Отправка формы приемки (Этап 1)
        async submitAcceptance() {
            if (!this.acceptForm.inventory_number || !this.acceptForm.name || !this.acceptForm.cabinet) {
                this.showToast('Заполните обязательные поля: Инв. №, Модель и Кабинет', 'error');
                return;
            }
            try {
                const payload = {
                    ...this.acceptForm,
                    branch_id: this.acceptForm.branch_id ? parseInt(this.acceptForm.branch_id) : (this.selectedBranchId ? parseInt(this.selectedBranchId) : null)
                };
                const res = await fetch('/api/v1/repair/equipment/accept', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Ошибка сохранения');
                }
                const saved = await res.json();
                this.showToast(`Техника "${saved.name}" (${saved.inventory_number}) принята в IT-отдел`, 'success');
                // Сброс формы приемки
                this.acceptForm.inventory_number = '';
                this.acceptForm.serial_number = '';
                this.acceptForm.name = '';
                this.acceptForm.notes = '';
                this.acceptForm.cabinet = '';
                this.acceptForm.current_user_id = '';
                this.acceptUserSearch = '';
                this.acceptIsNewAsset = false;
                this.acceptSuggestions = [];
                this.showAcceptEqDropdown = false;
                this.acceptEqNotFound = false;

                await this.loadEquipment();
                this.currentTab = 'send_sc';
            } catch (e) {
                this.showToast(e.message, 'error');
            }
        },

        // Ручное добавление техники
        openAddEquipment() {
            this.addForm = {
                inventory_number: '',
                serial_number: '',
                name: '',
                asset_type: 'workstation',
                condition: 'working',
                status: 'at_workplace',
                cabinet: '',
                branch_id: this.selectedBranchId || '',
                current_user_id: '',
                notes: ''
            };
            this.addSwitchConfig = {
                ip_address: '',
                management_type: 'omada',
                management_port: 8043,
                username: 'admin',
                password: '',
                snmp_community: 'public',
                total_ports: 24
            };
            this.switchTestResult = null;
            this.showAddModal = true;
        },

        async submitManualAdd() {
            if (!this.addForm.inventory_number || !this.addForm.name) {
                this.showToast('Укажите инвентарный номер и наименование', 'error');
                return;
            }
            try {
                const payload = {
                    ...this.addForm,
                    branch_id: this.addForm.branch_id ? parseInt(this.addForm.branch_id) : (this.selectedBranchId ? parseInt(this.selectedBranchId) : null),
                    switch_config: this.addForm.asset_type === 'switch' ? this.addSwitchConfig : null
                };
                const res = await fetch('/api/v1/repair/equipment', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Ошибка добавления');
                }
                this.showToast('Единица техники успешно зарегистрирована', 'success');
                this.showAddModal = false;
                await this.loadEquipment();
            } catch (e) {
                this.showToast(e.message, 'error');
            }
        },

        // Отправка в СЦ (Этап 2)
        async createSCBatch() {
            if (this.selectedForSC.length === 0) {
                this.showToast('Выберите хотя бы одну позицию для отправки', 'error');
                return;
            }
            if (!this.scVendorName.trim()) {
                this.showToast('Укажите сервисный центр', 'error');
                return;
            }
            try {
                const payload = {
                    vendor_name: this.scVendorName.trim(),
                    branch_id: this.selectedBranchId ? parseInt(this.selectedBranchId) : null,
                    notes: this.scBatchNotes,
                    asset_ids: this.selectedForSC
                };
                const res = await fetch('/api/v1/repair/batches', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Ошибка создания акта');
                }
                const newBatch = await res.json();
                this.showToast(`Акт ${newBatch.act_number} успешно сформирован!`, 'success');
                this.selectedForSC = [];
                await this.loadEquipment();
                await this.loadBatches();
                // Открываем печатную форму в новом окне
                window.open(`/print/repair-act/${newBatch.id}`, '_blank');
            } catch (e) {
                this.showToast(e.message, 'error');
            }
        },

        // Открытие модалки принятия из СЦ (Этап 3)
        openReturnModal(item) {
            this.returnTargetItem = item;
            this.returnForm = {
                diagnostic_result: 'Ремонт выполнен успешно',
                work_performed: 'Восстановление работоспособности',
                cost: 0,
                condition: 'working',
                notes: ''
            };
            this.showReturnModal = true;
        },

        // Подтверждение принятия из СЦ (Этап 3) — БЕЗ WHATSAPP!
        async submitReturnFromSC() {
            if (!this.returnTargetItem) return;
            try {
                const payload = {
                    asset_ids: [this.returnTargetItem.id],
                    diagnostic_result: this.returnForm.diagnostic_result,
                    work_performed: this.returnForm.work_performed,
                    cost: parseFloat(this.returnForm.cost) || 0,
                    condition: this.returnForm.condition,
                    notes: this.returnForm.notes
                };
                const res = await fetch('/api/v1/repair/equipment/return-sc', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Ошибка отметки о возврате');
                }
                this.showToast('Техника успешно принята из СЦ в IT-отдел (готова к установке)', 'success');
                this.showReturnModal = false;
                this.returnTargetItem = null;
                await this.loadEquipment();
                await this.loadBatches();
            } catch (e) {
                this.showToast(e.message, 'error');
            }
        },

        // Открытие модалки установки на рабочее место (Этап 4)
        openInstallModal(item) {
            this.installTargetItem = item;
            this.installForm = {
                cabinet: item.cabinet || '',
                current_user_id: item.current_user_id || '',
                notes: ''
            };
            this.showInstallModal = true;
        },

        // Подтверждение установки на рабочее место (Этап 4) — БЕЗ WHATSAPP!
        async submitInstallAtWorkplace() {
            if (!this.installTargetItem) return;
            try {
                const payload = {
                    asset_ids: [this.installTargetItem.id],
                    cabinet: this.installForm.cabinet,
                    current_user_id: this.installForm.current_user_id,
                    notes: this.installForm.notes
                };
                const res = await fetch('/api/v1/repair/equipment/install-workplace', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Ошибка установки техники');
                }
                this.showToast('Техника установлена и введена в эксплуатацию на рабочем месте!', 'success');
                this.showInstallModal = false;
                this.installTargetItem = null;
                await this.loadEquipment();
            } catch (e) {
                this.showToast(e.message, 'error');
            }
        },

        // Синхронизация компьютеров с Active Directory
        async triggerADSync() {
            this.isAdSyncing = true;
            try {
                let url = '/api/v1/repair/ad/sync-computers';
                if (this.selectedBranchId) url += `?branch_id=${this.selectedBranchId}`;
                const res = await fetch(url, {
                    method: 'POST',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast(data.message, 'success');
                    await this.loadEquipment();
                } else {
                    this.showToast(data.message || 'Ошибка сбора из AD', 'error');
                }
            } catch (e) {
                this.showToast('Сбой подключения к серверу AD', 'error');
            } finally {
                this.isAdSyncing = false;
            }
        },

        // Карточка подробностей оборудования и история
        async viewDetail(item) {
            try {
                const res = await fetch(`/api/v1/repair/equipment/${item.id}`, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.selectedEquipment = await res.json();
                    this.showDetailModal = true;
                }
            } catch (e) {
                console.error(e);
            }
        },

        // Редактирование оборудования
        openEditEquipment(item) {
            this.editForm = {
                id: item.id,
                inventory_number: item.inventory_number || '',
                serial_number: item.serial_number || '',
                name: item.name || '',
                asset_type: item.asset_type || 'workstation',
                condition: item.condition || 'working',
                status: item.status || 'at_workplace',
                cabinet: item.cabinet || '',
                branch_id: item.branch_id || '',
                current_user_id: item.current_user_id || '',
                notes: item.notes || ''
            };
            this.switchTestResult = null;
            if (item.switch_config) {
                this.editSwitchConfig = {
                    ip_address: item.switch_config.ip_address || '',
                    management_type: item.switch_config.management_type || 'omada',
                    management_port: item.switch_config.management_port || 8043,
                    username: item.switch_config.username || 'admin',
                    password: item.switch_config.password || '',
                    snmp_community: item.switch_config.snmp_community || 'public',
                    total_ports: item.switch_config.total_ports || 24
                };
            } else {
                this.editSwitchConfig = {
                    ip_address: '',
                    management_type: 'omada',
                    management_port: 8043,
                    username: 'admin',
                    password: '',
                    snmp_community: 'public',
                    total_ports: 24
                };
            }
            this.showEditModal = true;
        },

        async saveEquipmentEdit() {
            if (!this.editForm.id) return;
            try {
                const payload = {
                    ...this.editForm,
                    branch_id: this.editForm.branch_id ? parseInt(this.editForm.branch_id) : null,
                    switch_config: this.editForm.asset_type === 'switch' ? this.editSwitchConfig : null
                };
                const res = await fetch(`/api/v1/repair/equipment/${this.editForm.id}`, {
                    method: 'PUT',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    this.showToast('Оборудование успешно обновлено', 'success');
                    this.showEditModal = false;
                    if (this.selectedEquipment && this.selectedEquipment.id === this.editForm.id) {
                        this.selectedEquipment = await res.json();
                    }
                    await this.loadEquipment();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка обновления оборудования', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка отправки данных', 'error');
            }
        },

        async deleteEquipment(item) {
            if (!confirm(`Вы действительно хотите удалить единицу техники "${item.name} (${item.inventory_number})"?`)) {
                return;
            }
            try {
                const res = await fetch(`/api/v1/repair/equipment/${item.id}`, {
                    method: 'DELETE',
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    this.showToast('Оборудование успешно удалено', 'success');
                    if (this.showDetailModal && this.selectedEquipment?.id === item.id) {
                        this.showDetailModal = false;
                    }
                    await this.loadEquipment();
                } else {
                    let errMsg = 'Ошибка удаления';
                    try {
                        const err = await res.json();
                        errMsg = err.detail || err.message || errMsg;
                    } catch (_) {
                        errMsg = `Ошибка сервера (HTTP ${res.status})`;
                    }
                    this.showToast(errMsg, 'error');
                }
            } catch (e) {
                this.showToast(`Ошибка удаления оборудования: ${e.message}`, 'error');
            }
        },

        // --- УМНОЕ РАСПОЗНАВАНИЕ ТИПА И ХАРАКТЕРИСТИК ТЕХНИКИ ---
        async onEquipmentNameInput(formType) {
            const form = formType === 'add' ? this.addForm : (formType === 'edit' ? this.editForm : this.acceptForm);
            const name = (form.name || '').trim();
            if (name.length < 3) return;

            const lower = name.toLowerCase();
            if (lower.includes('коммутатор') || lower.includes('switch') || lower.includes('tl-sg') || lower.includes('procurve') || lower.includes('mikrotik') || lower.includes('omada') || lower.includes('edgecore') || lower.includes('catalyst')) {
                form.asset_type = 'switch';
                this.updateSwitchDefaultPort(formType);
            } else if (lower.includes('ноутбук') || lower.includes('laptop') || lower.includes('thinkpad') || lower.includes('latitude') || lower.includes('probook') || lower.includes('elitebook')) {
                form.asset_type = 'laptop';
            } else if (lower.includes('принтер') || lower.includes('мфу') || lower.includes('laserjet') || lower.includes('ecosys') || lower.includes('canon') || lower.includes('kyocera') || lower.includes('xerox') || lower.includes('epson')) {
                form.asset_type = 'printer';
            } else if (lower.includes('ибп') || lower.includes('ups') || lower.includes('apc') || lower.includes('smart-ups') || lower.includes('back-ups') || lower.includes('ippon')) {
                form.asset_type = 'ups';
            } else if (lower.includes('монитор') || lower.includes('monitor') || lower.includes('syncmaster') || lower.includes('ultrasharp')) {
                form.asset_type = 'monitor';
            } else if (lower.includes('пк') || lower.includes('pc') || lower.includes('prodesk') || lower.includes('elitedesk') || lower.includes('optiplex') || lower.includes('thinkcentre')) {
                form.asset_type = 'workstation';
            }

            try {
                const res = await fetch(`/api/v1/repair/models/suggest-specs?name=${encodeURIComponent(name)}`, {
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.suggested_category && (!form.asset_type || form.asset_type === 'other')) {
                        form.asset_type = data.suggested_category;
                    }
                    if (data.average_specs && (!form.notes || form.notes === '')) {
                        form.notes = `Характеристики: ${data.average_specs}`;
                    }
                }
            } catch (e) {
                console.error('Suggest specs error:', e);
            }
        },

        updateSwitchDefaultPort(formType) {
            const cfg = formType === 'add' ? this.addSwitchConfig : this.editSwitchConfig;
            const t = (cfg.management_type || 'snmp').toLowerCase();
            if (t === 'omada') cfg.management_port = 8043;
            else if (t === 'mikrotik' || t === 'ssh_cli') cfg.management_port = 22;
            else if (t === 'snmp') cfg.management_port = 161;
            else if (t === 'hp' || t === 'tplink') cfg.management_port = 23;
            else cfg.management_port = 22;
        },

        async testSwitchConnection(formType) {
            const cfg = formType === 'add' ? this.addSwitchConfig : this.editSwitchConfig;
            if (!cfg.ip_address || !cfg.ip_address.trim()) {
                this.showToast('Укажите IP-адрес коммутатора для проверки', 'error');
                return;
            }
            this.isTestingSwitch = true;
            this.switchTestResult = null;
            try {
                const res = await fetch('/api/v1/repair/equipment/test-switch-connection', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(cfg)
                });
                const data = await res.json();
                this.switchTestResult = data;
                if (data.success) {
                    this.showToast(data.message, 'success');
                } else {
                    this.showToast(data.message, 'error');
                }
            } catch (e) {
                this.switchTestResult = {
                    success: false,
                    message: `Сетевая ошибка при проверке: ${e.message}`
                };
                this.showToast(this.switchTestResult.message, 'error');
            } finally {
                this.isTestingSwitch = false;
            }
        },

        async syncSwitchEquipment(item) {
            if (!item || !item.id) return;
            try {
                this.showToast(`Опрос коммутатора ${item.name}...`, 'info');
                const res = await fetch(`/api/v1/repair/equipment/${item.id}/sync-switch`, {
                    method: 'POST',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    this.showToast(data.message || 'Синхронизация коммутатора выполнена успешно!', 'success');
                    await this.loadEquipment();
                    if (this.selectedEquipment && this.selectedEquipment.id === item.id) {
                        await this.viewDetail(item);
                    }
                } else {
                    this.showToast(data.message || data.detail || 'Ошибка опроса коммутатора', 'error');
                }
            } catch (e) {
                this.showToast(`Ошибка синхронизации: ${e.message}`, 'error');
            }
        },

        // --- СПРАВОЧНИК МОДЕЛЕЙ ---
        async syncModelsFromAD() {
            this.isSyncingModels = true;
            try {
                const res = await fetch('/api/v1/repair/models/sync-from-ad', {
                    method: 'POST',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast(data.message, 'success');
                    await this.loadModels();
                } else {
                    this.showToast(data.detail || 'Ошибка синхронизации моделей', 'error');
                }
            } catch (e) {
                this.showToast('Сетевой сбой при синхронизации моделей', 'error');
            } finally {
                this.isSyncingModels = false;
            }
        },

        async suggestSpecsForModel(force = false) {
            const name = (this.modelForm.name || '').trim();
            if (name.length < 2) return;
            try {
                const res = await fetch(`/api/v1/repair/models/suggest-specs?name=${encodeURIComponent(name)}`, {
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.suggested_vendor && (!this.modelForm.vendor || force)) {
                        this.modelForm.vendor = data.suggested_vendor;
                    }
                    if (data.suggested_category && (!this.modelForm.category || this.modelForm.category === 'other' || force)) {
                        this.modelForm.category = data.suggested_category;
                    }
                    if (data.average_specs && (!this.modelForm.specs_template || force)) {
                        this.modelForm.specs_template = data.average_specs;
                    }
                }
            } catch (e) {
                console.error('Suggest specs error:', e);
            }
        },

        onModelNameInput() {
            this.suggestSpecsForModel(false);
        },

        openCreateModel() {
            this.modelForm = {
                id: null,
                name: '',
                category: 'workstation',
                vendor: '',
                specs_template: '',
                notes: ''
            };
            this.showModelModal = true;
        },

        openEditModel(m) {
            this.modelForm = {
                id: m.id,
                name: m.name,
                category: m.category,
                vendor: m.vendor || '',
                specs_template: m.specs_template || '',
                notes: m.notes || ''
            };
            this.showModelModal = true;
        },

        async saveModel() {
            if (!this.modelForm.name.trim()) {
                this.showToast('Укажите наименование модели', 'error');
                return;
            }
            const isEdit = !!this.modelForm.id;
            const url = isEdit ? `/api/v1/repair/models/${this.modelForm.id}` : '/api/v1/repair/models';
            const method = isEdit ? 'PUT' : 'POST';

            try {
                const res = await fetch(url, {
                    method: method,
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(this.modelForm)
                });
                if (res.ok) {
                    this.showToast(isEdit ? 'Модель обновлена' : 'Модель добавлена', 'success');
                    this.showModelModal = false;
                    await this.loadModels();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка сохранения модели', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при сохранении', 'error');
            }
        },

        async deleteModel(m) {
            if (!confirm(`Удалить модель "${m.name}" из справочника?`)) return;
            try {
                const res = await fetch(`/api/v1/repair/models/${m.id}`, {
                    method: 'DELETE',
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    this.showToast('Модель удалена', 'success');
                    await this.loadModels();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка удаления', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка удаления модели', 'error');
            }
        },

        // Загрузка отчетов
        async loadReport() {
            this.isLoading = true;
            try {
                let url = '/api/v1/repair/reports/data?';
                if (this.selectedBranchId) url += `branch_id=${this.selectedBranchId}&`;
                if (this.reportFilterCondition) url += `condition_filter=${this.reportFilterCondition}&`;
                if (this.reportFilterType) url += `asset_type_filter=${this.reportFilterType}&`;
                if (this.reportSearch) url += `search=${encodeURIComponent(this.reportSearch)}&`;

                const res = await fetch(url, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    this.reportData = data.report;
                }
            } catch (e) {
                this.showToast('Ошибка загрузки отчета', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        // Выгрузка Excel отчета
        downloadExcelReport() {
            let url = '/api/v1/repair/reports/export/excel?';
            if (this.selectedBranchId) url += `branch_id=${this.selectedBranchId}&`;
            if (this.reportFilterCondition) url += `condition_filter=${this.reportFilterCondition}&`;
            if (this.reportFilterType) url += `asset_type_filter=${this.reportFilterType}&`;
            if (this.reportSearch) url += `search=${encodeURIComponent(this.reportSearch)}&`;
            
            // Скачивание через открытие окна с авторизационным заголовком через fetch blob
            fetch(url, { headers: this.getAuthHeaders() })
                .then(resp => resp.blob())
                .then(blob => {
                    const dlUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = dlUrl;
                    a.download = `equipment_report_${new Date().toISOString().slice(0, 10)}.xlsx`;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(dlUrl);
                })
                .catch(() => this.showToast('Ошибка выгрузки Excel', 'error'));
        },

        // Выход из системы
        logout() {
            localStorage.removeItem('token');
            window.location.href = '/';
        },

        // Вычисляемые списки для стадий
        get pendingSCItems() {
            return this.equipmentList.filter(e => e.status === 'pending_sc');
        },

        get atSCItems() {
            return this.equipmentList.filter(e => e.status === 'at_sc');
        },

        get returnedITItems() {
            return this.equipmentList.filter(e => e.status === 'returned_it');
        },

        get filteredModels() {
            return this.modelsList.filter(m => {
                if (this.modelCategoryFilter && m.category !== this.modelCategoryFilter) return false;
                if (this.modelSearchQuery) {
                    const q = this.modelSearchQuery.toLowerCase();
                    const nameMatch = m.name?.toLowerCase().includes(q);
                    const vendorMatch = m.vendor?.toLowerCase().includes(q);
                    const specsMatch = m.specs_template?.toLowerCase().includes(q);
                    if (!nameMatch && !vendorMatch && !specsMatch) return false;
                }
                return true;
            });
        },

        // Счетчики для бейджей на вкладках
        get counts() {
            return {
                all: this.equipmentList.length,
                pending_sc: this.pendingSCItems.length,
                at_sc: this.atSCItems.length,
                returned_it: this.returnedITItems.length,
                working: this.equipmentList.filter(e => e.condition === 'working').length,
                broken: this.equipmentList.filter(e => e.condition === 'broken').length,
                models: this.modelsList.length
            };
        }
    }));
});

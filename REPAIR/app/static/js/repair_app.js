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

        // Загрузки
        isLoading: false,
        isAdSyncing: false,

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
                const res = await fetch('/api/users/ad', { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.adUsers = await res.json();
                }
            } catch (e) {
                console.error(e);
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

        // Поиск по инвентарному номеру в форме приемки
        async searchInvForAccept() {
            const inv = this.acceptForm.inventory_number.trim();
            if (!inv) return;
            try {
                const res = await fetch(`/api/v1/repair/equipment/find-by-inv?query_str=${encodeURIComponent(inv)}`, {
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.found && data.equipment) {
                        const eq = data.equipment;
                        this.acceptForm.name = eq.name;
                        this.acceptForm.serial_number = eq.serial_number || '';
                        this.acceptForm.asset_type = eq.asset_type;
                        this.acceptForm.cabinet = eq.cabinet || '';
                        this.acceptForm.branch_id = eq.branch_id || this.selectedBranchId;
                        this.acceptForm.current_user_id = eq.current_user_id || '';
                        this.showToast(`Найдено: ${eq.name}`, 'info');
                    }
                }
            } catch (e) {
                console.error(e);
            }
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
                this.showToast('Техника успешно принята в IT-отдел (ожидает СЦ)', 'success');
                // Сброс формы
                this.acceptForm.inventory_number = '';
                this.acceptForm.serial_number = '';
                this.acceptForm.name = '';
                this.acceptForm.notes = '';
                await this.loadEquipment();
                this.currentTab = 'send_sc';
            } catch (e) {
                this.showToast(e.message, 'error');
            }
        },

        // Ручное добавление техники
        async submitManualAdd() {
            if (!this.addForm.inventory_number || !this.addForm.name) {
                this.showToast('Укажите инвентарный номер и наименование', 'error');
                return;
            }
            try {
                const payload = {
                    ...this.addForm,
                    branch_id: this.addForm.branch_id ? parseInt(this.addForm.branch_id) : (this.selectedBranchId ? parseInt(this.selectedBranchId) : null)
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

        // Счетчики для бейджей на вкладках
        get counts() {
            return {
                all: this.equipmentList.length,
                pending_sc: this.pendingSCItems.length,
                at_sc: this.atSCItems.length,
                returned_it: this.returnedITItems.length,
                working: this.equipmentList.filter(e => e.condition === 'working').length,
                broken: this.equipmentList.filter(e => e.condition === 'broken').length,
            };
        }
    }));
});

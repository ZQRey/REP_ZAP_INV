document.addEventListener('alpine:init', () => {
    Alpine.data('locationApp', () => ({
        token: localStorage.getItem('token') || '',
        currentUser: null,
        branches: [],
        selectedBranchId: '',
        
        floors: [],
        selectedFloorId: null,
        currentFloor: null,

        placedAssets: [],
        unplacedAssets: [],
        switchesList: [],

        selectedAsset: null,
        activeSwitch: null,
        showSwitchModal: false,
        showAssetModal: false,
        showAddAssetModal: false,
        isUploadingMap: false,

        // Настройка порта коммутатора
        showPortModal: false,
        selectedPort: null,
        portForm: {
            cabinet: '',
            socket_label: '',
            zone_id: '',
            vlan_id: 1,
            status: 'up',
            connected_asset_id: ''
        },

        // Настройка интеграции коммутатора (Omada, MikroTik, HP, TP-Link, SNMP)
        showSwitchSettingsModal: false,
        isPollingSwitch: false,
        switchForm: {
            id: null,
            name: '',
            ip_address: '',
            model: '',
            management_type: 'snmp',
            mgmt_port: 161,
            username: '',
            password: '',
            snmp_community: 'public',
            total_ports: 24,
            cabinet: '',
            site: 'Default'
        },

        // Симуляция роуминга
        showSimulateModal: false,
        simForm: {
            port_number: 1,
            mac_address: '',
            target_cabinet: ''
        },

        addAssetForm: {
            inventory_number: '',
            name: '',
            asset_type: 'workstation',
            serial_number: '',
            condition: 'working',
            cabinet: '',
            coords_x: 0.5,
            coords_y: 0.5,
            notes: ''
        },

        // Konva Canvas
        stage: null,
        zonesLayer: null,
        cablesLayer: null,
        assetsLayer: null,
        animLayer: null,
        animFrame: null,

        // Инструменты
        activeTool: 'select', // select, pan, draw_room
        isTracing: false,
        traceMessage: '',

        // Toast
        toast: { show: false, message: '', type: 'info' },

        showToast(msg, type = 'info') {
            this.toast.message = msg;
            this.toast.type = type;
            this.toast.show = true;
            setTimeout(() => { this.toast.show = false; }, 3500);
        },

        async init() {
            const urlParams = new URLSearchParams(window.location.search);
            const tokenParam = urlParams.get('token');
            if (tokenParam) {
                this.token = tokenParam;
                localStorage.setItem('token', tokenParam);
                window.history.replaceState({}, document.title, window.location.pathname);
            }

            if (!this.token) {
                window.location.href = '/?return_to=' + encodeURIComponent(window.location.pathname);
                return;
            }

            await this.loadCurrentUser();
            await this.loadBranches();
            
            // Инициализация холста Konva
            this.initKonva();

            if (this.branches.length > 0) {
                this.selectedBranchId = this.currentUser?.branch_id || this.branches[0].id;
                await this.loadFloors();
            }

            await this.loadUnplacedAssets();
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
                    window.location.href = '/';
                    return;
                }
                this.currentUser = await res.json();
            } catch (e) {
                console.error(e);
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

        async loadFloors() {
            if (!this.selectedBranchId) return;
            try {
                const res = await fetch(`/api/v1/location/branches/${this.selectedBranchId}/floors`, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.floors = await res.json();
                    if (this.floors.length > 0) {
                        this.selectedFloorId = this.floors[0].id;
                        this.selectFloor(this.floors[0]);
                    }
                }
            } catch (e) {
                console.error(e);
            }
        },

        async selectFloor(floor) {
            this.currentFloor = floor;
            this.selectedFloorId = floor.id;
            await this.loadFloorAssets();
            await this.loadFloorSwitches();
            this.renderFloor();
        },

        async loadFloorAssets() {
            if (!this.selectedFloorId) return;
            try {
                const res = await fetch(`/api/v1/location/floors/${this.selectedFloorId}/assets`, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.placedAssets = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        },

        async loadUnplacedAssets() {
            try {
                let url = '/api/v1/location/unplaced-assets';
                if (this.selectedBranchId) url += `?branch_id=${this.selectedBranchId}`;
                const res = await fetch(url, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.unplacedAssets = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        },

        async loadFloorSwitches() {
            if (!this.selectedFloorId) return;
            try {
                const res = await fetch(`/api/v1/location/floors/${this.selectedFloorId}/switches`, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.switchesList = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        },

        // Инициализация Konva.js
        initKonva() {
            const container = document.getElementById('canvas-container');
            const width = container.clientWidth || 1000;
            const height = container.clientHeight || 700;

            this.stage = new Konva.Stage({
                container: 'canvas-container',
                width: width,
                height: height,
                draggable: true
            });

            this.zonesLayer = new Konva.Layer();
            this.cablesLayer = new Konva.Layer();
            this.assetsLayer = new Konva.Layer();
            this.animLayer = new Konva.Layer();

            this.stage.add(this.zonesLayer);
            this.stage.add(this.cablesLayer);
            this.stage.add(this.assetsLayer);
            this.stage.add(this.animLayer);

            // Зум колесиком мыши
            const scaleBy = 1.08;
            this.stage.on('wheel', (e) => {
                e.evt.preventDefault();
                const oldScale = this.stage.scaleX();
                const pointer = this.stage.getPointerPosition();
                const mousePointTo = {
                    x: (pointer.x - this.stage.x()) / oldScale,
                    y: (pointer.y - this.stage.y()) / oldScale,
                };

                let newScale = e.evt.deltaY < 0 ? oldScale * scaleBy : oldScale / scaleBy;
                newScale = Math.max(0.4, Math.min(newScale, 3.5)); // Лимиты масштаба

                this.stage.scale({ x: newScale, y: newScale });
                const newPos = {
                    x: pointer.x - mousePointTo.x * newScale,
                    y: pointer.y - mousePointTo.y * newScale,
                };
                this.stage.position(newPos);
            });

            // Ресайз окна
            window.addEventListener('resize', () => {
                if (this.stage && container) {
                    this.stage.width(container.clientWidth);
                    this.stage.height(container.clientHeight);
                }
            });

            // Drag & Drop с HTML панели на холст
            container.addEventListener('dragover', (e) => e.preventDefault());
            container.addEventListener('drop', (e) => this.handleDropOnCanvas(e));
        },

        // Отрисовка плана этажа, зон и размещенных устройств
        renderFloor() {
            if (!this.stage || !this.currentFloor) return;

            this.zonesLayer.destroyChildren();
            this.cablesLayer.destroyChildren();
            this.assetsLayer.destroyChildren();

            const cWidth = this.stage.width();
            const cHeight = this.stage.height();

            // 0. Фоновое изображение поэтажного плана (если загружено)
            if (this.currentFloor.map_image_url) {
                const mapImg = new Image();
                mapImg.src = this.currentFloor.map_image_url;
                mapImg.onload = () => {
                    const konvaImg = new Konva.Image({
                        image: mapImg,
                        x: 0,
                        y: 0,
                        width: cWidth,
                        height: cHeight,
                        opacity: 0.9
                    });
                    this.zonesLayer.add(konvaImg);
                    konvaImg.moveToBottom();
                    this.zonesLayer.batchDraw();
                };
            }

            // 1. Отрисовка зон (Кабинетов и Коридоров)
            const zones = this.currentFloor.zones || [];
            zones.forEach(z => {
                if (!z.polygon_coords || z.polygon_coords.length < 3) return;

                const points = [];
                z.polygon_coords.forEach(pt => {
                    points.push(pt.x * cWidth);
                    points.push(pt.y * cHeight);
                });

                const poly = new Konva.Line({
                    points: points,
                    fill: z.fill_color || 'rgba(59, 130, 246, 0.15)',
                    stroke: z.border_color || '#3b82f6',
                    strokeWidth: 2,
                    closed: true
                });

                // Название комнаты
                const text = new Konva.Text({
                    x: points[0] + 10,
                    y: points[1] + 10,
                    text: `${z.name}\n${z.responsible_person ? 'Отв: ' + z.responsible_person : ''}`,
                    fontSize: 12,
                    fontFamily: 'Segoe UI, sans-serif',
                    fontStyle: 'bold',
                    fill: '#94a3b8'
                });

                this.zonesLayer.add(poly);
                this.zonesLayer.add(text);
            });

            // 2. Отрисовка коммутаторов
            this.switchesList.forEach(sw => {
                if (sw.coords_x === null || sw.coords_y === null) return;
                const px = sw.coords_x * cWidth;
                const py = sw.coords_y * cHeight;

                const group = new Konva.Group({
                    x: px,
                    y: py,
                    draggable: true
                });

                // Корпус коммутатора (Rack switch icon)
                const rect = new Konva.Rect({
                    x: -24,
                    y: -14,
                    width: 48,
                    height: 28,
                    fill: '#1e293b',
                    stroke: '#3b82f6',
                    strokeWidth: 2,
                    cornerRadius: 4,
                    shadowBlur: 8,
                    shadowColor: 'rgba(59, 130, 246, 0.4)'
                });

                const label = new Konva.Text({
                    x: -22,
                    y: -6,
                    text: 'SWITCH',
                    fontSize: 9,
                    fontStyle: 'bold',
                    fill: '#60a5fa'
                });

                // Индикатор питания
                const pwr = new Konva.Circle({
                    x: 16,
                    y: 0,
                    radius: 3,
                    fill: '#22c55e'
                });

                group.add(rect);
                group.add(label);
                group.add(pwr);

                group.on('click', () => {
                    this.openSwitchModal(sw);
                });

                group.on('dragend', () => {
                    const nx = group.x() / cWidth;
                    const ny = group.y() / cHeight;
                    this.updateAssetPos(sw.asset_id, nx, ny);
                });

                this.assetsLayer.add(group);
            });

            // 3. Отрисовка размещенных активов (ПК, принтеров)
            this.placedAssets.forEach(asset => {
                if (asset.coords_x === null || asset.coords_y === null) return;
                // Не дублируем свитчи
                if (asset.asset_type === 'switch') return;

                const ax = asset.coords_x * cWidth;
                const ay = asset.coords_y * cHeight;

                const group = new Konva.Group({
                    x: ax,
                    y: ay,
                    draggable: true
                });

                let statusColor = '#22c55e'; // active / working
                if (asset.condition === 'broken' || asset.status === 'at_sc' || asset.status === 'pending_sc') {
                    statusColor = '#ef4444'; // broken / repair
                }

                // Иконка устройства
                const circle = new Konva.Circle({
                    radius: 14,
                    fill: '#1e293b',
                    stroke: statusColor,
                    strokeWidth: 2,
                    shadowBlur: 6,
                    shadowColor: statusColor
                });

                // Буква типа (P = PC, L = Laptop, M = Monitor, PR = Printer)
                let typeLetter = 'PC';
                if (asset.asset_type === 'printer') typeLetter = 'PR';
                if (asset.asset_type === 'monitor') typeLetter = 'MO';
                if (asset.asset_type === 'laptop') typeLetter = 'NB';
                if (asset.asset_type === 'ups') typeLetter = 'UPS';

                const textLetter = new Konva.Text({
                    x: -8,
                    y: -5,
                    text: typeLetter,
                    fontSize: 10,
                    fontStyle: 'bold',
                    fill: '#f8fafc'
                });

                // Индикатор состояния
                const statusDot = new Konva.Circle({
                    x: 10,
                    y: -10,
                    radius: 4,
                    fill: statusColor
                });

                // Подпись инвентарного номера
                const invText = new Konva.Text({
                    x: -35,
                    y: 18,
                    text: asset.inventory_number,
                    fontSize: 10,
                    fontStyle: 'bold',
                    fill: '#cbd5e1'
                });

                group.add(circle);
                group.add(textLetter);
                group.add(statusDot);
                group.add(invText);

                group.on('click', () => {
                    this.selectedAsset = asset;
                    this.showAssetModal = true;
                });

                group.on('dragend', () => {
                    const nx = group.x() / cWidth;
                    const ny = group.y() / cHeight;
                    this.updateAssetPos(asset.id, nx, ny);
                });

                this.assetsLayer.add(group);
            });

            this.zonesLayer.batchDraw();
            this.assetsLayer.batchDraw();
        },

        // Обновление координат актива на сервере
        async updateAssetPos(assetId, normX, normY) {
            try {
                await fetch(`/api/v1/location/assets/${assetId}/position`, {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({
                        coords_x: normX,
                        coords_y: normY,
                        floor_id: this.selectedFloorId
                    })
                });
                this.showToast('Положение сохранено', 'info');
                await this.loadFloorAssets();
                await this.loadFloorSwitches();
            } catch (e) {
                this.showToast('Ошибка сохранения позиции', 'error');
            }
        },

        // Drop с боковой панели на холст
        async handleDropOnCanvas(e) {
            e.preventDefault();
            const assetDataStr = e.dataTransfer.getData('application/json');
            if (!assetDataStr) return;

            const asset = JSON.parse(assetDataStr);
            const container = document.getElementById('canvas-container');
            const rect = container.getBoundingClientRect();

            // Точные координаты относительно контейнера с учетом зума и панорамирования
            const clientX = e.clientX - rect.left;
            const clientY = e.clientY - rect.top;

            const oldScale = this.stage.scaleX();
            const stagePos = this.stage.position();

            const canvasX = (clientX - stagePos.x) / oldScale;
            const canvasY = (clientY - stagePos.y) / oldScale;

            const normX = Math.max(0.02, Math.min(0.98, canvasX / this.stage.width()));
            const normY = Math.max(0.02, Math.min(0.98, canvasY / this.stage.height()));

            await this.updateAssetPos(asset.id, normX, normY);
            await this.loadUnplacedAssets();
            this.renderFloor();
        },

        // Трассировка кабеля от коммутатора к активу
        async traceCableToAsset(asset) {
            if (this.switchesList.length === 0) {
                this.showToast('На этаже нет коммутаторов для трассировки', 'error');
                return;
            }

            const sw = this.switchesList[0];
            this.isTracing = true;
            this.traceMessage = `Трассировка кабеля: ${sw.name} -> ${asset.inventory_number}...`;

            try {
                const res = await fetch(`/api/v1/location/network/trace?from_switch=${sw.id}&to_asset=${asset.id}`, {
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (data.found && data.path_points.length >= 2) {
                    this.showToast(data.message, 'success');
                    this.animateCablePath(data.path_points);
                } else {
                    this.showToast(data.message || 'Трасса не найдена', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка расчета трассы', 'error');
            } finally {
                this.isTracing = false;
            }
        },

        // Анимация бегущего импульса по кабелю (Konva Animation)
        animateCablePath(points) {
            this.animLayer.destroyChildren();
            if (this.animFrame) {
                this.animFrame.stop();
            }

            const cWidth = this.stage.width();
            const cHeight = this.stage.height();

            const flatPoints = [];
            points.forEach(p => {
                flatPoints.push(p.x * cWidth);
                flatPoints.push(p.y * cHeight);
            });

            // Базовая светящаяся линия
            const baseLine = new Konva.Line({
                points: flatPoints,
                stroke: 'rgba(59, 130, 246, 0.4)',
                strokeWidth: 4,
                lineCap: 'round',
                lineJoin: 'round'
            });

            // Импульсная линия с бегущим пунктиром
            const pulseLine = new Konva.Line({
                points: flatPoints,
                stroke: '#60a5fa',
                strokeWidth: 3,
                dash: [12, 10],
                shadowColor: '#38bdf8',
                shadowBlur: 10,
                lineCap: 'round',
                lineJoin: 'round'
            });

            this.animLayer.add(baseLine);
            this.animLayer.add(pulseLine);
            this.animLayer.batchDraw();

            let animOffset = 0;
            this.animFrame = new Konva.Animation(() => {
                animOffset -= 1.5;
                pulseLine.dashOffset(animOffset);
            }, this.animLayer);

            this.animFrame.start();
        },

        // Открытие панели портов коммутатора
        openSwitchModal(sw) {
            this.activeSwitch = sw;
            this.showSwitchModal = true;
        },

        // Сброс масштаба и центрирование
        resetZoom() {
            if (this.stage) {
                this.stage.scale({ x: 1, y: 1 });
                this.stage.position({ x: 0, y: 0 });
                this.stage.batchDraw();
            }
        },

        triggerUploadFloorMap() {
            if (!this.selectedFloorId) {
                this.showToast('Выберите этаж для загрузки плана', 'error');
                return;
            }
            const input = document.getElementById('floorMapUploadInput');
            if (input) input.click();
        },

        async uploadFloorMap(event) {
            const file = event.target.files?.[0];
            if (!file || !this.selectedFloorId) return;

            this.isUploadingMap = true;
            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch(`/api/v1/location/floors/${this.selectedFloorId}/upload-map`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${this.token}` },
                    body: formData
                });
                if (res.ok) {
                    const data = await res.json();
                    this.showToast('План этажа успешно загружен', 'success');
                    if (this.currentFloor) {
                        this.currentFloor.map_image_url = data.map_image_url;
                    }
                    this.renderFloor();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка загрузки плана', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при загрузке плана', 'error');
            } finally {
                this.isUploadingMap = false;
                event.target.value = '';
            }
        },

        openAddAssetModal() {
            if (!this.selectedFloorId) {
                this.showToast('Сначала выберите этаж', 'error');
                return;
            }
            this.addAssetForm = {
                inventory_number: '',
                name: '',
                asset_type: 'workstation',
                serial_number: '',
                condition: 'working',
                cabinet: '',
                coords_x: 0.5,
                coords_y: 0.5,
                notes: ''
            };
            this.showAddAssetModal = true;
        },

        async submitAddAsset() {
            if (!this.addAssetForm.inventory_number.trim() || !this.addAssetForm.name.trim()) {
                this.showToast('Укажите инвентарный номер и наименование', 'error');
                return;
            }

            try {
                const payload = {
                    ...this.addAssetForm,
                    floor_id: parseInt(this.selectedFloorId),
                    branch_id: this.selectedBranchId ? parseInt(this.selectedBranchId) : null
                };
                const res = await fetch('/api/v1/location/assets/create-and-place', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    this.showToast('Оборудование создано и размещено на карте!', 'success');
                    this.showAddAssetModal = false;
                    await this.loadFloorAssets();
                    await this.loadUnplacedAssets();
                    this.renderFloor();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка создания актива', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при создании актива', 'error');
            }
        },

        // ==========================================
        // УПРАВЛЕНИЕ И ИНТЕГРАЦИЯ КОММУТАТОРА
        // ==========================================
        openSwitchSettingsModal(sw) {
            this.switchForm = {
                id: sw.id,
                name: sw.name,
                ip_address: sw.ip_address,
                model: sw.model || '24-Port Managed Switch',
                management_type: sw.management_type || 'snmp',
                mgmt_port: sw.mgmt_port || 161,
                username: sw.username || '',
                password: '',
                snmp_community: sw.snmp_community || 'public',
                total_ports: sw.total_ports || 24,
                cabinet: sw.cabinet || '',
                site: (sw.extra_params && sw.extra_params.site) || 'Default'
            };
            this.showSwitchSettingsModal = true;
        },

        async saveSwitchSettings() {
            if (!this.switchForm.id) return;
            try {
                const payload = {
                    name: this.switchForm.name,
                    ip_address: this.switchForm.ip_address,
                    model: this.switchForm.model,
                    management_type: this.switchForm.management_type,
                    mgmt_port: parseInt(this.switchForm.mgmt_port),
                    username: this.switchForm.username,
                    snmp_community: this.switchForm.snmp_community,
                    total_ports: parseInt(this.switchForm.total_ports),
                    cabinet: this.switchForm.cabinet,
                    extra_params: {
                        site: this.switchForm.site,
                        allow_demo_fallback: true
                    }
                };
                if (this.switchForm.password) {
                    payload.password = this.switchForm.password;
                }

                const res = await fetch(`/api/v1/location/switches/${this.switchForm.id}`, {
                    method: 'PUT',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    this.showToast('Параметры коммутатора сохранены', 'success');
                    this.showSwitchSettingsModal = false;
                    await this.loadFloorSwitches();
                    const updated = this.switchesList.find(s => s.id === this.switchForm.id);
                    if (updated) this.activeSwitch = updated;
                    this.renderFloor();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка сохранения настроек', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при сохранении настроек', 'error');
            }
        },

        async pollSwitch(sw) {
            if (!sw) return;
            this.isPollingSwitch = true;
            try {
                const res = await fetch(`/api/v1/location/switches/${sw.id}/poll`, {
                    method: 'POST',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok) {
                    let msg = `Опрос завершен. Обнаружено MAC: ${data.learned_count}`;
                    if (data.relocated_assets && data.relocated_assets.length > 0) {
                        msg += `. ПЕРЕМЕЩЕНО устройств: ${data.relocated_assets.length}!`;
                        data.relocated_assets.forEach(rel => {
                            this.showToast(`Перемещение: ${rel.name} (${rel.inventory_number}) -> ${rel.new_cabinet}`, 'info');
                        });
                    }
                    this.showToast(msg, data.relocated_assets?.length > 0 ? 'success' : 'info');
                    await this.loadFloorSwitches();
                    await this.loadFloorAssets();
                    const updated = this.switchesList.find(s => s.id === sw.id);
                    if (updated) this.activeSwitch = updated;
                    this.renderFloor();
                } else {
                    this.showToast(data.detail || data.message || 'Ошибка опроса коммутатора', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка связи с сервером при опросе', 'error');
            } finally {
                this.isPollingSwitch = false;
            }
        },

        // ==========================================
        // НАСТРОЙКА ПОРТА И ПРИВЯЗКА К КАБИНЕТУ
        // ==========================================
        openPortSettingsModal(p) {
            this.selectedPort = p;
            this.portForm = {
                cabinet: p.cabinet || '',
                socket_label: p.socket_label || '',
                zone_id: p.zone_id || '',
                vlan_id: p.vlan_id || 1,
                status: p.status || 'down',
                connected_asset_id: p.connected_asset_id || ''
            };
            this.showPortModal = true;
        },

        async savePortSettings() {
            if (!this.activeSwitch || !this.selectedPort) return;
            try {
                const payload = {
                    cabinet: this.portForm.cabinet,
                    socket_label: this.portForm.socket_label,
                    zone_id: this.portForm.zone_id ? parseInt(this.portForm.zone_id) : null,
                    vlan_id: parseInt(this.portForm.vlan_id) || 1,
                    status: this.portForm.status,
                    connected_asset_id: this.portForm.connected_asset_id ? parseInt(this.portForm.connected_asset_id) : null
                };

                const res = await fetch(`/api/v1/location/switches/${this.activeSwitch.id}/ports/${this.selectedPort.port_number}`, {
                    method: 'PUT',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    this.showToast(`Порт ${this.selectedPort.port_number} успешно настроен`, 'success');
                    this.showPortModal = false;
                    await this.loadFloorSwitches();
                    const updated = this.switchesList.find(s => s.id === this.activeSwitch.id);
                    if (updated) this.activeSwitch = updated;
                    this.renderFloor();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка сохранения настроек порта', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при настройке порта', 'error');
            }
        },

        openSimulateModal(p) {
            this.selectedPort = p;
            this.simForm = {
                port_number: p.port_number,
                mac_address: p.last_mac || '00:1A:2B:3C:4D:5E',
                target_cabinet: p.cabinet || 'Кабинет 302'
            };
            this.showSimulateModal = true;
        },

        async submitSimulateEvent() {
            if (!this.activeSwitch) return;
            try {
                const res = await fetch(`/api/v1/location/switches/${this.activeSwitch.id}/simulate-event`, {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(this.simForm)
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast(data.message, 'success');
                    if (data.relocated_assets && data.relocated_assets.length > 0) {
                        data.relocated_assets.forEach(rel => {
                            this.showToast(`Оборудование ${rel.name} переехало в ${rel.new_cabinet}!`, 'success');
                        });
                    }
                    this.showSimulateModal = false;
                    if (this.showPortModal) this.showPortModal = false;
                    await this.loadFloorSwitches();
                    await this.loadFloorAssets();
                    const updated = this.switchesList.find(s => s.id === this.activeSwitch.id);
                    if (updated) this.activeSwitch = updated;
                    this.renderFloor();
                } else {
                    this.showToast(data.detail || 'Ошибка симуляции', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка симуляции', 'error');
            }
        },

        logout() {
            localStorage.removeItem('token');
            window.location.href = '/';
        }
    }));
});

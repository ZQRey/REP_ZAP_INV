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
        allPlacedAssets: [],
        switchesList: [],

        // Вкладки и фильтрация активов
        assetsTab: 'unplaced', // 'unplaced' | 'placed'
        assetSearch: '',
        assetTypeFilter: 'all',
        assetNetFilter: 'all',

        // Модалка быстрого перемещения / назначения в кабинет
        showAssignModal: false,
        assignAsset: null,
        assignFloorZones: [],
        assignForm: {
            floor_id: '',
            zone_id: '',
            cabinet: ''
        },

        get filteredUnplacedAssets() {
            let list = this.unplacedAssets || [];
            if (this.assetTypeFilter && this.assetTypeFilter !== 'all') {
                list = list.filter(a => a.asset_type === this.assetTypeFilter);
            }
            if (this.assetSearch && this.assetSearch.trim()) {
                const q = this.assetSearch.trim().toLowerCase();
                list = list.filter(a => {
                    const inv = (a.inventory_number || '').toLowerCase();
                    const name = (a.name || '').toLowerCase();
                    const cab = (a.cabinet || '').toLowerCase();
                    const host = (a.hostname || '').toLowerCase();
                    const ip = (a.ip_address || '').toLowerCase();
                    const mac = (a.mac_address || '').toLowerCase();
                    return inv.includes(q) || name.includes(q) || cab.includes(q) || host.includes(q) || ip.includes(q) || mac.includes(q);
                });
            }
            return list;
        },

        get filteredPlacedAssets() {
            let list = (this.allPlacedAssets && this.allPlacedAssets.length > 0) ? this.allPlacedAssets : (this.placedAssets || []);
            if (this.assetTypeFilter && this.assetTypeFilter !== 'all') {
                list = list.filter(a => a.asset_type === this.assetTypeFilter);
            }
            if (this.assetNetFilter && this.assetNetFilter !== 'all') {
                list = list.filter(a => a.network_location_status === this.assetNetFilter);
            }
            if (this.assetSearch && this.assetSearch.trim()) {
                const q = this.assetSearch.trim().toLowerCase();
                list = list.filter(a => {
                    const inv = (a.inventory_number || '').toLowerCase();
                    const name = (a.name || '').toLowerCase();
                    const cab = (a.cabinet || '').toLowerCase();
                    const fl = (a.floor_name || '').toLowerCase();
                    const zn = (a.zone_name || '').toLowerCase();
                    const sw = (a.connected_switch_name || '').toLowerCase();
                    const swCab = (a.connected_cabinet || '').toLowerCase();
                    const host = (a.hostname || '').toLowerCase();
                    const ip = (a.ip_address || '').toLowerCase();
                    const mac = (a.mac_address || '').toLowerCase();
                    return inv.includes(q) || name.includes(q) || cab.includes(q) || fl.includes(q) || zn.includes(q) || sw.includes(q) || swCab.includes(q) || host.includes(q) || ip.includes(q) || mac.includes(q);
                });
            }
            return list;
        },

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

        // Добавление нового коммутатора с профилями производителей
        showAddSwitchModal: false,
        isTestingConnection: false,
        connectionTestResult: null,
        copiedCliSnippet: false,
        selectedSwitchVendor: 'cisco',
        newSwitchForm: {
            name: 'SW-CORE-01',
            inventory_number: '',
            ip_address: '192.168.1.1',
            model: 'Cisco Catalyst 2960X / 9200',
            management_type: 'ssh_cli',
            mgmt_port: 22,
            username: 'admin',
            password: '',
            snmp_community: 'public',
            total_ports: 24,
            cabinet: 'Серверная',
            site: 'Default',
            coords_x: 0.25,
            coords_y: 0.25
        },
        switchVendorProfiles: {
            cisco: {
                title: 'Cisco Catalyst / CBS',
                icon: 'cisco',
                badge: 'SSH CLI / SNMP',
                model: 'Cisco Catalyst 2960X / 9200',
                management_type: 'ssh_cli',
                mgmt_port: 22,
                username: 'admin',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Опрос таблицы MAC-адресов по протоколу SSH (show mac address-table) или по SNMP v2c.',
                cli_guide: `enable
configure terminal
hostname SW-CORE
ip domain-name company.local
crypto key generate rsa modulus 2048
ip ssh version 2
username admin privilege 15 secret YourPassword
line vty 0 15
 transport input ssh
 login local
 exit
snmp-server community public RO
write memory`,
                notes: 'Для SSH убедитесь, что учетная запись имеет privilege 15 или права на команду show mac address-table.'
            },
            mikrotik: {
                title: 'MikroTik RouterOS / SwOS',
                icon: 'mikrotik',
                badge: 'SSH / Bridge Host',
                model: 'MikroTik Cloud Router Switch CRS328 / CRS326',
                management_type: 'mikrotik',
                mgmt_port: 22,
                username: 'admin',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Чтение таблицы хостов сетевого моста через SSH CLI (/interface bridge host print) или SNMP v2c.',
                cli_guide: `/user add name=it_monitor group=read password=YourPassword
/ip service enable ssh
/ip service set ssh port=22
/snmp set enabled=yes
/snmp community set [ find default=yes ] addresses=0.0.0.0/0 name=public read-access=yes`,
                notes: 'Для работы через SSH достаточно создать пользователя в группе "read". Система автоматически сопоставляет ether-интерфейсы с портами.'
            },
            tplink_omada: {
                title: 'TP-Link Omada SDN',
                icon: 'omada',
                badge: 'Controller API (HTTPS)',
                model: 'TP-Link Omada TL-SG3428X / SG3210',
                management_type: 'omada',
                mgmt_port: 8043,
                username: 'admin',
                total_ports: 24,
                site: 'Default',
                snmp_community: 'public',
                description: 'Прямая интеграция с контроллером Omada SDN (аппаратный OC200/OC300 или программный контроллер) через REST API.',
                cli_guide: `1. Откройте веб-интерфейс контроллера Omada: https://<IP_КОНТРОЛЛЕРА>:8043
2. Перейдите в Settings -> Global Settings / Administrators.
3. Добавьте учетную запись пользователя с ролью "Viewer" или "Administrator".
4. Укажите название сайта (по умолчанию "Default").
5. Убедитесь, что порт 8043 (HTTPS) доступен для сервера учета.`,
                notes: 'Контроллер централизованно отслеживает переподключение техники и роуминг между коммутаторами и точками доступа Wi-Fi.'
            },
            tplink_jetstream: {
                title: 'TP-Link JetStream (Standalone)',
                icon: 'tplink',
                badge: 'SSH CLI / SNMP',
                model: 'TP-Link JetStream T2600G-28TS / TL-SG3428',
                management_type: 'tplink',
                mgmt_port: 22,
                username: 'admin',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Опрос управляемых коммутаторов TP-Link в автономном режиме через SSH CLI или SNMP v2c.',
                cli_guide: `enable
configure
service ssh
snmp-server community public ro
copy running-config startup-config`,
                notes: 'Через веб-интерфейс: Security -> Access Security -> SSH Config (Enable SSH) и Management -> SNMP -> SNMP Config (Enable SNMP Agent).'
            },
            hp_aruba: {
                title: 'HP / Aruba ProCurve',
                icon: 'hp',
                badge: 'SSH CLI / SNMP',
                model: 'HP ProCurve 2530 / Aruba 2930F / 2540',
                management_type: 'hp',
                mgmt_port: 22,
                username: 'manager',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Чтение таблицы FDB через команду "show mac-address" по SSH либо по протоколу SNMP v2c.',
                cli_guide: `configure
crypto key generate ssh rsa
ip ssh
password manager user-name manager
snmp-server community "public" unrestricted
write memory`,
                notes: 'В HP ProCurve порт указывается в формате "1", "2" или "A1", "B2". Система автоматически распознает цифровой номер порта.'
            },
            huawei: {
                title: 'Huawei CloudEngine / Quidway',
                icon: 'huawei',
                badge: 'Stelnet (SSH) / SNMP',
                model: 'Huawei S5720 / S5735 / CloudEngine',
                management_type: 'ssh_cli',
                mgmt_port: 22,
                username: 'admin',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Опрос таблицы MAC-адресов через Stelnet (SSH CLI) с командой "display mac-address" или SNMP v2c.',
                cli_guide: `system-view
rsa local-key-pair create
stelnet server enable
ssh user admin authentication-type password
ssh user admin service-type stelnet
snmp-agent
snmp-agent sys-info version v2c
snmp-agent community read public
save`,
                notes: 'Убедитесь, что для пользователя admin включена служба stelnet и задан пароль.'
            },
            dlink: {
                title: 'D-Link Smart / Managed',
                icon: 'dlink',
                badge: 'SNMP v2c / Bridge MIB',
                model: 'D-Link DGS-1210 / DGS-1510 / DES-3200',
                management_type: 'snmp',
                mgmt_port: 161,
                username: 'admin',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Стандартный опрос FDB-таблицы по SNMP v2c Bridge-MIB (OID 1.3.6.1.2.1.17.4.3.1.2) либо через SSH/Telnet.',
                cli_guide: `enable snmp
create snmp community public view restricted read_only
enable ssh
save`,
                notes: 'В веб-интерфейсе D-Link: Management -> SNMP Settings -> включить SNMP v2c и создать Community "public" с правами Read-Only.'
            },
            eltex: {
                title: 'Eltex MES',
                icon: 'eltex',
                badge: 'SSH CLI / SNMP',
                model: 'Eltex MES2428 / MES2324 / MES3324',
                management_type: 'ssh_cli',
                mgmt_port: 22,
                username: 'admin',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Чтение таблицы коммутации по протоколу SSH (show mac address-table) или SNMP v2c.',
                cli_guide: `configure
crypto key generate rsa
ip ssh server
username admin privilege 15 password YourPassword
snmp-server server
snmp-server community public ro
end
write`,
                notes: 'Отечественные коммутаторы Eltex MES поддерживают стандартный синтаксис Cisco-like CLI.'
            },
            generic: {
                title: 'Универсальный SNMP L2/L3',
                icon: 'generic',
                badge: 'IEEE 802.1D Bridge-MIB',
                model: 'Generic Managed L2/L3 Switch (Zyxel, Keenetic, Netgear, Ruijie)',
                management_type: 'snmp',
                mgmt_port: 161,
                username: '',
                total_ports: 24,
                snmp_community: 'public',
                description: 'Подходит для любых управляемых коммутаторов с поддержкой отраслевого стандарта SNMP v2c Bridge-MIB dot1dTpFdbTable.',
                cli_guide: `1. Войдите в веб-интерфейс коммутатора.
2. Найдите раздел "SNMP Configuration" / "Управление по SNMP".
3. Включите SNMP Agent (версия v2c).
4. Задайте имя сообщества (Community Name): "public" (только чтение - RO).
5. Разрешите входящие UDP пакеты на порт 161 от IP-адреса сервера системы учета.`,
                notes: 'Стандарт Bridge-MIB поддерживается 99% всех управляемых L2/L3 коммутаторов в мире.'
            }
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
            await this.loadAllPlacedAssets();
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
                        await this.selectFloor(this.floors[0]);
                    }
                    await this.loadAllPlacedAssets();
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

        async loadAllPlacedAssets() {
            try {
                let url = '/api/v1/location/placed-assets';
                if (this.selectedBranchId) url += `?branch_id=${this.selectedBranchId}`;
                const res = await fetch(url, { headers: this.getAuthHeaders() });
                if (res.ok) {
                    this.allPlacedAssets = await res.json();
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
                await this.loadAllPlacedAssets();
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
            await this.loadAllPlacedAssets();
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

        // Переход и центрирование камеры на объекте (поиск на карте)
        async focusAsset(asset) {
            if (!asset) return;

            // Если объект размещен на другом этаже, сначала переключаемся на нужный этаж
            if (asset.floor_id && asset.floor_id != this.selectedFloorId) {
                const targetFloor = this.floors.find(f => f.id == asset.floor_id);
                if (targetFloor) {
                    await this.selectFloor(targetFloor);
                    setTimeout(() => {
                        this.panAndHighlightAsset(asset);
                    }, 300);
                    return;
                }
            }

            this.panAndHighlightAsset(asset);
        },

        // Плавная анимация камеры к координатам актива и световая индикация
        panAndHighlightAsset(asset) {
            if (!this.stage) return;

            if (asset.coords_x == null || asset.coords_y == null) {
                this.showToast('Объект не имеет точных координат на плане этажа. Нажмите "Переместить", чтобы привязать к кабинету.', 'info');
                return;
            }

            const cWidth = this.stage.width();
            const cHeight = this.stage.height();
            const ax = asset.coords_x * cWidth;
            const ay = asset.coords_y * cHeight;
            const targetScale = 1.75;

            const newX = (cWidth / 2) - (ax * targetScale);
            const newY = (cHeight / 2) - (ay * targetScale);

            new Konva.Tween({
                node: this.stage,
                duration: 0.5,
                x: newX,
                y: newY,
                scaleX: targetScale,
                scaleY: targetScale,
                easing: Konva.Easings.EaseInOut
            }).play();

            this.pulseHighlightRing(ax, ay);

            // Информативное оповещение
            if (asset.network_location_status === 'roaming') {
                this.showToast(`⚠️ РОУМИНГ: ${asset.name} (${asset.inventory_number}) обнаружен в "${asset.connected_cabinet || 'другом порту'}"!`, 'info');
            } else if (asset.connected_switch_name) {
                this.showToast(`📍 ${asset.name} (${asset.inventory_number}): ${asset.cabinet || 'Кабинет'} [SW: ${asset.connected_switch_name}, порт ${asset.connected_port_number}]`, 'info');
            } else {
                this.showToast(`📍 ${asset.name} (${asset.inventory_number}): ${asset.cabinet || 'Кабинет не указан'}`, 'info');
            }
        },

        // Пульсирующее неоновое кольцо подсветки найденного актива
        pulseHighlightRing(x, y) {
            if (!this.animLayer) return;

            const outerRing = new Konva.Circle({
                x: x,
                y: y,
                radius: 18,
                stroke: '#a855f7',
                strokeWidth: 4,
                shadowColor: '#c084fc',
                shadowBlur: 16,
                opacity: 1
            });

            const innerRing = new Konva.Circle({
                x: x,
                y: y,
                radius: 8,
                fill: 'rgba(168, 85, 247, 0.45)'
            });

            this.animLayer.add(innerRing);
            this.animLayer.add(outerRing);
            this.animLayer.batchDraw();

            const tween = new Konva.Tween({
                node: outerRing,
                duration: 1.4,
                radius: 64,
                strokeWidth: 1,
                opacity: 0,
                easing: Konva.Easings.EaseOut,
                onFinish: () => {
                    outerRing.destroy();
                    innerRing.destroy();
                    this.animLayer.batchDraw();
                }
            });
            tween.play();
        },

        // Открытие модалки перемещения / назначения в кабинет
        openAssignCabinetModal(asset) {
            this.assignAsset = asset;
            const defaultFloorId = asset.floor_id || this.selectedFloorId || (this.floors[0] ? this.floors[0].id : '');
            this.assignForm = {
                floor_id: defaultFloorId,
                zone_id: asset.zone_id || '',
                cabinet: asset.cabinet || ''
            };
            this.updateAssignFloorZones();
            this.showAssignModal = true;
        },

        onAssignFloorChanged() {
            this.updateAssignFloorZones();
            this.assignForm.zone_id = '';
        },

        updateAssignFloorZones() {
            if (!this.assignForm.floor_id) {
                this.assignFloorZones = [];
                return;
            }
            const floor = this.floors.find(f => f.id == this.assignForm.floor_id);
            this.assignFloorZones = (floor && floor.zones) ? floor.zones : [];
        },

        onAssignZoneSelected(zoneId) {
            if (!zoneId) return;
            const zone = this.assignFloorZones.find(z => z.id == zoneId);
            if (zone) {
                this.assignForm.cabinet = zone.name;
            }
        },

        async submitAssignCabinet() {
            if (!this.assignAsset) return;
            if (!this.assignForm.cabinet || !this.assignForm.cabinet.trim()) {
                this.showToast('Укажите название кабинета', 'error');
                return;
            }

            try {
                const payload = {
                    cabinet: this.assignForm.cabinet.trim(),
                    floor_id: this.assignForm.floor_id ? parseInt(this.assignForm.floor_id) : null,
                    zone_id: this.assignForm.zone_id ? parseInt(this.assignForm.zone_id) : null
                };

                const res = await fetch(`/api/v1/location/assets/${this.assignAsset.id}/assign-cabinet`, {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const updated = await res.json();
                    this.showToast(`Устройство ${updated.name} размещено в "${updated.cabinet || 'кабинете'}"!`, 'success');
                    this.showAssignModal = false;

                    await this.loadUnplacedAssets();
                    await this.loadAllPlacedAssets();

                    if (updated.floor_id == this.selectedFloorId) {
                        await this.loadFloorAssets();
                        this.renderFloor();
                        this.focusAsset(updated);
                    } else if (updated.floor_id) {
                        const targetFloor = this.floors.find(f => f.id == updated.floor_id);
                        if (targetFloor) {
                            await this.selectFloor(targetFloor);
                            setTimeout(() => this.focusAsset(updated), 300);
                        }
                    }
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка перемещения в кабинет', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при перемещении актива', 'error');
            }
        },

        async unplaceAsset(asset) {
            if (!asset) return;
            if (!confirm(`Снять "${asset.name}" (${asset.inventory_number}) с поэтажного плана? Он вернется в неразмещенные активы.`)) {
                return;
            }

            try {
                const res = await fetch(`/api/v1/location/assets/${asset.id}/unplace`, {
                    method: 'POST',
                    headers: this.getAuthHeaders()
                });
                if (res.ok) {
                    this.showToast(`Актив ${asset.inventory_number} возвращен в неразмещенные`, 'info');
                    await this.loadFloorAssets();
                    await this.loadUnplacedAssets();
                    await this.loadAllPlacedAssets();
                    this.renderFloor();
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка снятия с карты', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при снятии с карты', 'error');
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
                    await this.loadAllPlacedAssets();
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
                    await this.loadAllPlacedAssets();
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
        // СОЗДАНИЕ И ИНТЕГРАЦИЯ НОВОГО КОММУТАТОРА
        // ==========================================
        openAddSwitchModal() {
            this.connectionTestResult = null;
            this.copiedCliSnippet = false;
            this.selectSwitchVendor('cisco');
            this.newSwitchForm.name = 'SW-CORE-01';
            this.newSwitchForm.inventory_number = '';
            this.newSwitchForm.ip_address = '192.168.1.1';
            this.newSwitchForm.cabinet = 'Серверная';
            this.newSwitchForm.coords_x = 0.25;
            this.newSwitchForm.coords_y = 0.25;
            this.showAddSwitchModal = true;
        },

        selectSwitchVendor(vKey) {
            this.selectedSwitchVendor = vKey;
            this.connectionTestResult = null;
            const profile = this.switchVendorProfiles[vKey];
            if (profile) {
                this.newSwitchForm.model = profile.model;
                this.newSwitchForm.management_type = profile.management_type;
                this.newSwitchForm.mgmt_port = profile.mgmt_port;
                this.newSwitchForm.username = profile.username;
                this.newSwitchForm.snmp_community = profile.snmp_community || 'public';
                this.newSwitchForm.total_ports = profile.total_ports || 24;
                if (profile.site) this.newSwitchForm.site = profile.site;
            }
        },

        copyCliSnippet(text) {
            if (!text) return;
            navigator.clipboard.writeText(text).then(() => {
                this.copiedCliSnippet = true;
                this.showToast('Инструкция настройки скопирована в буфер обмена', 'success');
                setTimeout(() => { this.copiedCliSnippet = false; }, 2500);
            }).catch(() => {
                this.showToast('Не удалось скопировать текст в буфер', 'error');
            });
        },

        async testSwitchConnection(formType = 'new') {
            const form = formType === 'new' ? this.newSwitchForm : this.switchForm;
            if (!form.ip_address) {
                this.showToast('Укажите IP-адрес для проверки связи', 'warning');
                return;
            }

            this.isTestingConnection = true;
            this.connectionTestResult = null;
            try {
                const payload = {
                    ip_address: form.ip_address,
                    management_type: form.management_type,
                    mgmt_port: parseInt(form.mgmt_port) || null,
                    username: form.username || null,
                    password: form.password || null,
                    snmp_community: form.snmp_community || 'public',
                    extra_params: {
                        site: form.site || 'Default'
                    }
                };

                const res = await fetch('/api/v1/location/switches/test-connection', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                this.connectionTestResult = data;
                if (data.status === 'ok') {
                    this.showToast(data.message, 'success');
                } else if (data.status === 'warning') {
                    this.showToast(data.message, 'warning');
                } else {
                    this.showToast(data.message || 'Ошибка проверки связи', 'error');
                }
            } catch (e) {
                this.connectionTestResult = {
                    success: false,
                    reachable: false,
                    status: 'error',
                    message: 'Сетевая ошибка при выполнении проверки связи'
                };
                this.showToast('Ошибка сети при тесте подключения', 'error');
            } finally {
                this.isTestingConnection = false;
            }
        },

        async saveNewSwitch() {
            if (!this.newSwitchForm.name || !this.newSwitchForm.ip_address) {
                this.showToast('Заполните наименование и IP-адрес коммутатора', 'warning');
                return;
            }
            if (!this.selectedFloorId) {
                this.showToast('Выберите этаж для размещения коммутатора', 'warning');
                return;
            }

            try {
                const payload = {
                    name: this.newSwitchForm.name.trim(),
                    inventory_number: this.newSwitchForm.inventory_number ? this.newSwitchForm.inventory_number.trim() : null,
                    ip_address: this.newSwitchForm.ip_address.trim(),
                    floor_id: this.selectedFloorId,
                    branch_id: this.selectedBranchId,
                    model: this.newSwitchForm.model ? this.newSwitchForm.model.trim() : 'L2 Managed Switch',
                    management_type: this.newSwitchForm.management_type,
                    mgmt_port: parseInt(this.newSwitchForm.mgmt_port) || 161,
                    username: this.newSwitchForm.username ? this.newSwitchForm.username.trim() : null,
                    password: this.newSwitchForm.password ? this.newSwitchForm.password.trim() : null,
                    snmp_community: this.newSwitchForm.snmp_community ? this.newSwitchForm.snmp_community.trim() : 'public',
                    total_ports: parseInt(this.newSwitchForm.total_ports) || 24,
                    cabinet: this.newSwitchForm.cabinet ? this.newSwitchForm.cabinet.trim() : 'Серверная',
                    coords_x: this.newSwitchForm.coords_x || 0.25,
                    coords_y: this.newSwitchForm.coords_y || 0.25,
                    extra_params: {
                        site: this.newSwitchForm.site || 'Default',
                        vendor: this.selectedSwitchVendor,
                        allow_demo_fallback: false
                    }
                };

                const res = await fetch('/api/v1/location/switches', {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const created = await res.json();
                    this.showToast(`Коммутатор "${created.name}" успешно добавлен! Портов: ${created.total_ports}`, 'success');
                    this.showAddSwitchModal = false;
                    await this.loadFloorSwitches();
                    await this.loadFloorAssets();
                    this.renderFloor();
                    const newlyAdded = this.switchesList.find(s => s.id === created.id);
                    if (newlyAdded) {
                        this.openSwitchModal(newlyAdded);
                    }
                } else {
                    const err = await res.json();
                    this.showToast(err.detail || 'Ошибка добавления коммутатора', 'error');
                }
            } catch (e) {
                this.showToast('Сетевая ошибка при добавлении коммутатора', 'error');
            }
        },

        async deleteSwitch(sw) {
            if (!sw) return;
            const confirmMsg = `Вы действительно хотите удалить коммутатор "${sw.name}" (${sw.ip_address})?\n\nВсе порты и привязки к розеткам будут очищены. Это действие необратимо.`;
            if (!confirm(confirmMsg)) return;

            try {
                const res = await fetch(`/api/v1/location/switches/${sw.id}`, {
                    method: 'DELETE',
                    headers: this.getAuthHeaders()
                });
                const data = await res.json();
                if (res.ok) {
                    this.showToast(data.message || 'Коммутатор успешно удален', 'success');
                    this.showSwitchModal = false;
                    this.showSwitchSettingsModal = false;
                    this.activeSwitch = null;
                    await this.loadFloorSwitches();
                    await this.loadFloorAssets();
                    this.renderFloor();
                } else {
                    this.showToast(data.detail || data.message || 'Ошибка удаления коммутатора', 'error');
                }
            } catch (e) {
                this.showToast('Ошибка сети при удалении коммутатора', 'error');
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
                    await this.loadAllPlacedAssets();
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

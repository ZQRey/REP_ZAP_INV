import sys
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "CARTRIDGE"))

from main_server import app
from SHARED.database import SessionLocal, init_db
from SHARED.models import Asset, NetworkSwitch, SwitchPort, EquipmentHistoryLog

def run_tests():
    init_db()
    client = TestClient(app)

    # 1. Login as admin
    login_res = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'admin123', 'auth_type': 'local'})
    assert login_res.status_code == 200, f'Login failed: {login_res.text}'
    token = login_res.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # 2. Get floor switches
    sw_res = client.get('/api/v1/location/floors/1/switches', headers=headers)
    assert sw_res.status_code == 200, f'Switches error: {sw_res.text}'
    switches = sw_res.json()
    assert len(switches) > 0, 'No switches found'
    sw = switches[0]
    sw_id = sw['id']
    print(f"[+] Switch #{sw_id} ({sw['name']}) loaded, management_type: {sw['management_type']}, total ports: {sw['total_ports']}")

    # 3. Update Port 5 to be mapped to 'Кабинет 305' and 'Розетка 305-1'
    port_update_res = client.put(f'/api/v1/location/switches/{sw_id}/ports/5', headers=headers, json={
        'cabinet': 'Кабинет 305',
        'socket_label': 'Розетка 305-1',
        'vlan_id': 20,
        'status': 'up'
    })
    assert port_update_res.status_code == 200, f'Port update error: {port_update_res.text}'
    port_data = port_update_res.json()
    assert port_data['cabinet'] == 'Кабинет 305'
    assert port_data['socket_label'] == 'Розетка 305-1'
    print('[+] Switch Port 5 successfully mapped to cabinet: Кабинет 305, socket: Розетка 305-1')

    # 4. Create an Asset with specific MAC address currently located in 'Кабинет 101'
    db = SessionLocal()
    test_mac = '00:1A:2B:3C:4D:99'
    asset = db.query(Asset).filter(Asset.inventory_number == 'TEST-ROAM-PC').first()
    if not asset:
        asset = Asset(
            inventory_number='TEST-ROAM-PC',
            name='Рабочая станция инженера',
            asset_type='workstation',
            status='at_workplace',
            condition='working',
            branch_id=1,
            floor_id=1,
            cabinet='Кабинет 101',
            mac_address=test_mac
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
    else:
        asset.cabinet = 'Кабинет 101'
        asset.mac_address = test_mac
        db.commit()

    print(f'[+] Created/found test asset #{asset.id} ({asset.name}) in cabinet: {asset.cabinet}, MAC: {asset.mac_address}')
    db.close()

    # 5. Simulate roaming event: PC moves to another room and is plugged into Port 5!
    sim_res = client.post(f'/api/v1/location/switches/{sw_id}/simulate-event', headers=headers, json={
        'port_number': 5,
        'mac_address': test_mac
    })
    assert sim_res.status_code == 200, f'Simulate error: {sim_res.text}'
    sim_data = sim_res.json()
    print('[+] Roaming simulation response:', sim_data)
    assert len(sim_data['relocated_assets']) > 0, 'Asset was not recognized as relocated'
    rel = sim_data['relocated_assets'][0]
    assert rel['old_cabinet'] == 'Кабинет 101'
    assert rel['new_cabinet'] == 'Кабинет 305'
    print(f"[+] SUCCESS: Device {rel['name']} moved from {rel['old_cabinet']} to {rel['new_cabinet']}!")

    # 6. Verify Asset in database and history
    db = SessionLocal()
    updated_asset = db.query(Asset).filter(Asset.inventory_number == 'TEST-ROAM-PC').first()
    assert updated_asset.cabinet == 'Кабинет 305', f'Asset cabinet is {updated_asset.cabinet}, expected Кабинет 305'

    history_entry = db.query(EquipmentHistoryLog).filter(
        EquipmentHistoryLog.asset_id == updated_asset.id,
        EquipmentHistoryLog.action.ilike('%перемещение%')
    ).order_by(EquipmentHistoryLog.id.desc()).first()
    assert history_entry is not None, 'History entry not found'
    print(f'[+] History log recorded: action="{history_entry.action}", details="{history_entry.details}"')
    db.close()

    # 7. Test switch poll endpoint
    poll_res = client.post(f'/api/v1/location/switches/{sw_id}/poll', headers=headers)
    assert poll_res.status_code == 200, f'Poll error: {poll_res.text}'
    print('[+] Poll switch result:', poll_res.json())

    # 8. Test switch integration update (Omada / MikroTik / HP / TP-Link)
    sw_put = client.put(f'/api/v1/location/switches/{sw_id}', headers=headers, json={
        'management_type': 'omada',
        'mgmt_port': 8043,
        'username': 'omada_admin',
        'model': 'TP-Link Omada SG3428X'
    })
    assert sw_put.status_code == 200, f'Switch put error: {sw_put.text}'
    updated_sw = sw_put.json()
    assert updated_sw['management_type'] == 'omada'
    assert updated_sw['mgmt_port'] == 8043
    print('[+] Switch management settings updated to Omada SDN successfully')

    print('\n*** ALL SWITCH L2 INTEGRATION & ROAMING TESTS PASSED 100%! ***')

if __name__ == '__main__':
    run_tests()

"""Read-only Omada Open API client-credentials integration."""
import ssl
import httpx
from SHARED.network_policy import validate_device_address
from SHARED.transport_security import tls_context
from SHARED.logging_security import register_secret


def poll_openapi(switch, normalize_mac):
    cfg = switch.extra_params or {}
    host = cfg.get("controller_host") or switch.ip_address
    validate_device_address(host)
    controller_id = cfg.get("controller_id")
    site_id = cfg.get("site_id")
    switch_mac = normalize_mac(cfg.get("switch_mac", ""))
    if not controller_id or not site_id or not switch_mac or not switch.username or not switch.password:
        raise ValueError("Omada requires Controller ID, Site ID, switch MAC and Client ID / Client Secret")
    certificate = cfg.get("controller_certificate")
    if certificate:
        # Trust the explicitly configured controller certificate only. Omada's
        # factory certificate has SAN=Omada instead of the management IP.
        context = ssl.create_default_context(cadata=certificate)
        context.check_hostname = False
    else:
        context = tls_context()
    base = f"https://{host}:{switch.mgmt_port or 8043}"
    register_secret(switch.password)
    with httpx.Client(base_url=base, verify=context, timeout=20, follow_redirects=False) as client:
        response = client.post("/openapi/authorize/token", params={"grant_type": "client_credentials"},
            json={"omadacId": controller_id, "client_id": switch.username, "client_secret": switch.password})
        response.raise_for_status()
        data = response.json()
        token = data.get("result", {}).get("accessToken")
        if data.get("errorCode") != 0 or not token:
            raise ConnectionError("Omada Open API credentials rejected")
        register_secret(token)
        client.headers["Authorization"] = "AccessToken=" + token
        rows = []
        for page in range(1, 1001):
            response = client.get(f"/openapi/v1/{controller_id}/sites/{site_id}/clients",
                params={"page": page, "pageSize": 100})
            response.raise_for_status()
            data = response.json()
            if data.get("errorCode") != 0:
                raise ConnectionError("Omada Open API client query rejected")
            result = data.get("result", {})
            clients = result.get("data", [])
            for device in clients:
                if normalize_mac(device.get("switchMac", "")) != switch_mac or device.get("active") is False:
                    continue
                mac = normalize_mac(device.get("mac", ""))
                try:
                    port = int(device.get("port", 0))
                except (TypeError, ValueError):
                    continue
                if mac and 1 <= port <= switch.total_ports:
                    rows.append({"port": port, "mac": mac, "ip": device.get("ip")})
            total = result.get("totalRows")
            if not clients or (total is not None and page * 100 >= int(total)) or (total is None and len(clients) < 100):
                return rows
        raise ConnectionError("Omada pagination limit exceeded")

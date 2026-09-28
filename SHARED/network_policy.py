"""Bound device-management requests to explicitly configured IP networks."""
import ipaddress
import os
from SHARED.security_config import PRODUCTION


def validate_device_address(address):
    networks = os.getenv("NETWORK_ALLOWED_CIDRS", "")
    if not PRODUCTION and not networks:
        return
    try:
        ip = ipaddress.ip_address(address)
        allowed = [ipaddress.ip_network(n.strip()) for n in networks.split(",") if n.strip()]
    except ValueError:
        raise ValueError("Device IP or NETWORK_ALLOWED_CIDRS is invalid") from None
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or not any(ip in n for n in allowed):
        raise ValueError("Device IP is outside the permitted management networks")

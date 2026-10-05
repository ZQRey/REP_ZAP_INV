"""Verified transports: no trust-on-first-use and no plaintext LDAP binds."""
import ssl
from SHARED.security_config import TLS_CA_FILE, SSH_KNOWN_HOSTS, LDAP_ALLOW_PLAINTEXT


def tls_context():
    return ssl.create_default_context(cafile=TLS_CA_FILE)


def ssh_client():
    import paramiko
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if SSH_KNOWN_HOSTS:
        client.load_host_keys(SSH_KNOWN_HOSTS)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    return client


def ldap_connection(host, port, use_ssl, user, password, timeout=5):
    from ldap3 import Server, Connection, Tls, NONE, AUTO_BIND_NO_TLS, AUTO_BIND_TLS_BEFORE_BIND
    if not user or not password:
        raise ValueError("LDAP credentials required")
    from SHARED.logging_security import register_secret
    register_secret(password)
    server = Server(host, port=port, use_ssl=use_ssl, get_info=NONE, connect_timeout=timeout,
                    tls=Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=TLS_CA_FILE))
    if use_ssl:
        auto_bind = AUTO_BIND_NO_TLS
    elif LDAP_ALLOW_PLAINTEXT:
        auto_bind = AUTO_BIND_NO_TLS
    else:
        auto_bind = AUTO_BIND_TLS_BEFORE_BIND
    return Connection(
        server,
        user=user,
        password=password,
        read_only=True,
        auto_bind=auto_bind,
        receive_timeout=timeout,
    )

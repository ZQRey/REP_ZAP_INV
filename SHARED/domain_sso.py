"""Verify Kerberos tickets locally. Client-supplied identity headers are never trusted."""
import base64
import binascii
import hashlib
import ipaddress
import re

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from SHARED.authentication import require_superadmin
from SHARED.database import get_db
from SHARED.models import AppUser, ADUser
from SHARED.config import BD_DIR
from CARTRIDGE.app.services.settings_service import SettingsService

router = APIRouter(prefix='/api/v1/auth', tags=['Domain SSO'])
KEYTAB = BD_DIR / 'sso' / 'http.keytab'


def validate_settings(values):
    if values.get('sso_enabled') != 'true':
        return
    if not values.get('ad_host') or not values.get('ad_base_dn'):
        raise HTTPException(422, 'Сначала настройте LDAP')
    hostname = values.get('sso_hostname', '').strip().lower()
    realm = values.get('sso_realm', '').strip().upper()
    try:
        ipaddress.ip_address(hostname)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip or not re.fullmatch(r'(?=.{1,253}$)[a-z0-9]+(?:[.-][a-z0-9]+)+', hostname):
        raise HTTPException(422, 'Укажите DNS-имя сайта без протокола и порта')
    if not re.fullmatch(r'[A-Z0-9]+(?:[.-][A-Z0-9]+)+', realm):
        raise HTTPException(422, 'Укажите Kerberos realm, например EXAMPLE.LOCAL')
    if not KEYTAB.is_file():
        raise HTTPException(422, 'Сначала загрузите сервисный keytab')


def accept_ticket(ticket, values):
    import gssapi
    name = gssapi.Name('HTTP/' + values['sso_hostname'].strip().lower() + '@' + values['sso_realm'].strip().upper(),
                       name_type=gssapi.NameType.kerberos_principal)
    creds = gssapi.Credentials(name=name, usage='accept', store={'keytab': str(KEYTAB)})
    context = gssapi.SecurityContext(creds=creds, usage='accept')
    output = context.step(ticket)
    if not context.complete or context.mech != gssapi.MechType.kerberos:
        raise ValueError('Kerberos authentication not complete')
    return str(context.initiator_name), output


def resolve_user(db, principal, realm):
    username, separator, ticket_realm = principal.rpartition('@')
    if not separator or ticket_realm.upper() != realm.strip().upper() or not re.fullmatch(r'[\w.\-$]{1,128}', username):
        raise HTTPException(403, 'Доменная учётная запись не разрешена')
    # Ambiguous aliases and local accounts must not be taken over through SSO.
    matches = db.query(AppUser).filter(func.lower(AppUser.username).in_([username.lower(), principal.lower()])).all()
    if len(matches) > 1 or any(u.auth_type != 'ad' or not u.is_active for u in matches):
        raise HTTPException(403, 'Доменная учётная запись не разрешена')
    if matches:
        user = matches[0]
    else:
        profile = db.query(ADUser).filter(func.lower(ADUser.samaccountname) == username.lower()).first()
        user = AppUser(username=username, full_name=profile.display_name if profile else username,
                       auth_type='ad', role='user', is_active=True, branch_id=None, password_hash=None)
        db.add(user)
    from SHARED.user_branch import sync_cartridge_owner_branch
    sync_cartridge_owner_branch(db, user)
    db.commit()
    db.refresh(user)
    return user


@router.get('/sso/status')
def sso_status(request: Request, db: Session = Depends(get_db)):
    values = SettingsService.get_all(db)
    enabled = False
    if values.get('sso_enabled') == 'true':
        try:
            validate_settings(values)
            enabled = request.url.scheme == 'https' and request.url.hostname == values['sso_hostname'].strip().lower()
        except HTTPException:
            pass
    return {'enabled': enabled}


@router.get('/sso')
def domain_login(request: Request, db: Session = Depends(get_db)):
    values = SettingsService.get_all(db)
    if values.get('sso_enabled') != 'true':
        raise HTTPException(404, 'Автоматический вход выключен')
    validate_settings(values)
    if request.url.scheme != 'https' or request.url.hostname != values['sso_hostname'].strip().lower():
        raise HTTPException(403, 'Для автоматического входа используйте HTTPS и настроенное DNS-имя')
    authorization = request.headers.get('authorization', '')
    if not authorization:
        return JSONResponse({'detail': 'Domain authentication required'}, 401, headers={'WWW-Authenticate': 'Negotiate'})
    from SHARED.login_security import check_login
    check_login(request, 'domain-sso-' + hashlib.sha256(authorization.encode()).hexdigest())
    try:
        scheme, encoded = authorization.split(' ', 1)
        if scheme.lower() != 'negotiate' or len(encoded) > 65536:
            raise ValueError()
        ticket = base64.b64decode(encoded, validate=True)
        principal, output = accept_ticket(ticket, values)
    except (ValueError, binascii.Error):
        raise HTTPException(401, 'Не удалось проверить доменную авторизацию') from None
    except Exception:
        # No ticket, key material, or GSS error details may escape into responses/logs.
        raise HTTPException(401, 'Доменная авторизация недоступна') from None
    user = resolve_user(db, principal, values['sso_realm'])
    from SHARED.tokens import create_access_token
    headers = {'WWW-Authenticate': 'Negotiate ' + base64.b64encode(output).decode()} if output else {}
    return JSONResponse({'access_token': create_access_token({'sub': user.username}), 'token_type': 'bearer'}, headers=headers)


@router.post('/sso/keytab')
async def upload_keytab(file: UploadFile = File(...), user=Depends(require_superadmin)):
    data = await file.read(65537)
    if len(data) < 8 or len(data) > 65536 or data[:2] not in (b'\x05\x01', b'\x05\x02'):
        raise HTTPException(422, 'Ожидается keytab размером до 64 КБ')
    KEYTAB.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    import os
    import tempfile
    from pathlib import Path
    descriptor, temporary_name = tempfile.mkstemp(dir=KEYTAB.parent, suffix='.tmp')
    temporary = Path(temporary_name)
    with os.fdopen(descriptor, 'wb') as target:
        target.write(data)
    temporary.replace(KEYTAB)
    return {'success': True}

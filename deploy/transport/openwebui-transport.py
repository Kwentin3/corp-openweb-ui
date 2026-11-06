#!/usr/bin/python3
"""Select one upstream in the existing Privoxy; no parallel selection state."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

CONFIG=Path('/etc/privoxy/config')
BACKUPS=Path('/root/transport-awg-20261106')
RULE=re.compile(r'^[ \t]*(?:forward-socks5t|forward)[ \t]+/[ \t]+[^\r\n]+',re.MULTILINE)

def active(unit):
    return subprocess.run(['systemctl','is-active','--quiet',unit]).returncode==0

def routes():
    cfg=json.loads(Path('/usr/local/etc/xray/config.json').read_text())
    inbound=next(x for x in cfg['inbounds'] if x['protocol']=='socks')
    assert inbound['listen']=='127.0.0.1'
    account=inbound['settings']['accounts'][0]
    auth=urllib.parse.quote(account['user'],safe='')+':'+urllib.parse.quote(account['pass'],safe='')
    return {'xray':'forward-socks5t / '+auth+'@127.0.0.1:'+str(inbound['port'])+' .','awg':'forward / 10.203.0.2:8119'}

def selected(text,choices):
    rules=RULE.findall(text)
    if len(rules)!=1:return 'unknown'
    return next((name for name,rule in choices.items() if rules[0].strip()==rule),'unknown')

def atomic_write(payload):
    metadata=CONFIG.stat()
    with tempfile.NamedTemporaryFile(dir=CONFIG.parent,prefix='.transport-',delete=False) as handle:
        temporary=Path(handle.name)
        try:
            handle.write(payload);handle.flush();os.fsync(handle.fileno())
            os.fchmod(handle.fileno(),metadata.st_mode & 0o777)
            os.fchown(handle.fileno(),metadata.st_uid,metadata.st_gid)
            # Privoxy3.0.34 checks time_t mtime, not inode or nanoseconds.
            modified=max(int(time.time()),int(metadata.st_mtime)+1)
            os.utime(temporary,(modified,modified))
            os.replace(temporary,CONFIG)
        finally:temporary.unlink(missing_ok=True)

def reload_native():
    assert active('privoxy'),'Privoxy inactive'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'http':'http://127.0.0.1:8118'}))
    # Native config reload may take one or two new client connections.
    for _ in range(2):
        with opener.open('http://config.privoxy.org/show-status',timeout=4) as response:response.read(65536)

def probe(proxy='http://127.0.0.1:8118'):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':proxy}))
    try:
        with opener.open('https://api.openai.com/v1/models',timeout=20) as response:status=response.status
    except urllib.error.HTTPError as error:status=error.code
    assert status==401,'Expected unauthenticated API reachability'

def preflight(target,choices):
    if target=='awg':
        probe('http://10.203.0.2:8119')
    else:
        upstream=choices['xray'].split()[2]
        config='silent\nshow-error\noutput = "/dev/null"\nnoproxy = ""\nconnect-timeout = 8\nmax-time = 20\nurl = "https://api.openai.com/v1/models"\nproxy = '+json.dumps('socks5h://'+upstream)+'\n'
        result=subprocess.run(['curl','--config','-','--write-out','%{http_code}'],input=config,text=True,capture_output=True,timeout=24)
        assert result.returncode==0 and result.stdout=='401','Xray backend is not reachable'

def main():
    if os.geteuid()!=0:raise RuntimeError('Run as root')
    choices=routes();original=CONFIG.read_bytes();text=original.decode()
    if sys.argv[1:]==['status']:
        print(json.dumps({'selected':selected(text,choices),'privoxy_active':active('privoxy'),'xray_active':active('xray'),'awg_active':active('amneziawg-egress'),'awg_proxy_active':active('privoxy-awg-egress')}));return
    if len(sys.argv)!=3 or sys.argv[1]!='use' or sys.argv[2] not in choices:
        raise RuntimeError('Usage: openwebui-transport status | use xray | use awg')
    target=sys.argv[2];previous=selected(text,choices)
    assert previous!='unknown','Unexpected forwarding rules; leave untouched'
    assert active('xray') if target=='xray' else active('amneziawg-egress') and active('privoxy-awg-egress'),'Selected backend inactive'
    if previous==target:
        probe();print(json.dumps({'selected':target,'changed':False,'api_reachable':True}));return
    preflight(target,choices)
    candidate=RULE.sub(lambda _:choices[target],text).encode()
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir='/etc/privoxy',prefix='.transport-',delete=False) as handle:
            temporary=Path(handle.name);handle.write(candidate)
        p=subprocess.run(['privoxy','--config-test',str(temporary)],capture_output=True,text=True,timeout=8)
        assert p.returncode==0,'Privoxy rejected candidate; diagnostics withheld'
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    BACKUPS.mkdir(mode=0o700,exist_ok=True)
    backup=BACKUPS/('switch-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+previous+'.before')
    backup.write_bytes(original);backup.chmod(0o600)
    assert CONFIG.read_bytes()==original,'Concurrent Privoxy change; leave untouched'
    try:
        atomic_write(candidate);reload_native();probe()
    except Exception:
        atomic_write(original);reload_native()
        raise RuntimeError('Switch failed; previous configuration restored') from None
    print(json.dumps({'selected':target,'previous':previous,'changed':True,'api_reachable':True,'native_reload':True,'backup':str(backup)}))

if __name__=='__main__':
    try:
        with open('/run/lock/openwebui-transport.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            main()
    except Exception as error:
        # Native backend/config errors can contain secret-bearing source lines.
        message=str(error) if isinstance(error,(AssertionError,RuntimeError)) else 'Native operation failed; inspect service status'
        print(json.dumps({'error_type':type(error).__name__,'message':message,'operation_failed':True}),file=sys.stderr);sys.exit(1)

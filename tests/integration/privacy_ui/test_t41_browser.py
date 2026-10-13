"""Actual Edge, Cookie/CSRF, HTTP and PostgreSQL rights workflow; no API fixtures."""
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,unquote
from uuid import uuid4
from datetime import timedelta
import json,mimetypes,os,secrets,subprocess,threading
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from services.api.app.api.rights import create_rights_app
from services.api.app.auth.grants.schemas import SharingSettings,CreateGrantInput,AcceptGrantInput
from services.api.app.auth.grants.policy import POLICY_VERSION,POLICY_HASH
from services.api.app.auth.grants.service import SharingService
from services.api.app.auth.models import AuthOwnedResource
from services.api.app.privacy.rights.schemas import RightsPolicy,OwnerConfirmation
from services.api.app.privacy.rights.service import RightsService
from services.api.app.privacy.rights.models import RightsRequest
from tests.integration.privacy_rights.test_t40_safety import admitted,attach

ROOT=Path(__file__).resolve().parents[3]
BUILD=ROOT/'.cache/t41-auth-frontend-validation'
pytestmark=pytest.mark.postgres

class Bridge(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*_):pass
    def send(self,status,data=b'',headers=()):
        try:
            self.send_response(status)
            for name,value in headers:
                if name.lower() not in {'content-length','connection','transfer-encoding'}:self.send_header(name,value)
            self.send_header('Content-Length',str(len(data)));self.send_header('Connection','close');self.end_headers()
            if self.command!='HEAD':self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
        self.close_connection=True
    def handle_request(self):
        path=urlsplit(self.path).path
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:self.send(400);return
        if not 0<=length<=16384:self.send(413);return
        body=self.rfile.read(length) if length else b''
        if path=='/__t41/control':
            if not secrets.compare_digest(self.headers.get('X-T41-Control',''),self.server.control):self.send(403);return
            action=json.loads(body or b'{}').get('action') if self.command=='POST' else None
            case=self.server.case
            if action=='arm':self.server.armed=True
            elif action=='release':self.server.release.set()
            elif action in {'run','fail','retry'}:
                worker=case.rights
                if action=='retry':
                    case.io.fail_delete=False
                    with Session(case.rights.store.engine) as session:
                        row=session.scalar(select(RightsRequest).where(RightsRequest.kind=='deletion'))
                        identifier=row.id
                    worker=RightsService(case.auth,case.rights.store,case.guard,RightsPolicy(enabled=True,allow_test_rights=True,max_attempts=2))
                    worker.retry_deletion(identifier)
                case.io.fail_delete=action=='fail'
                lease=worker.claim(uuid4())
                assert lease is not None
                self.server.worker_result=worker.run(lease).model_dump(mode='json')
            elif action is not None:self.send(422);return
            self.send(200,json.dumps({'blocked':self.server.blocked.is_set(),'completed':self.server.completed.is_set(),
                'delayed_status':self.server.delayed_status,'worker':self.server.worker_result}).encode(),(('Content-Type','application/json'),('Cache-Control','no-store')));return
        if path.startswith('/api/'):
            headers=[(k,v) for k,v in self.headers.raw_items() if k.lower() not in {'content-length','connection','transfer-encoding','x-t41-control'}]
            response=self.server.client.request(self.command,self.path[4:],content=body,headers=headers,follow_redirects=False)
            delayed=self.server.armed and self.command=='GET' and path.endswith('/content')
            if delayed:
                self.server.armed=False;self.server.delayed_status=response.status_code;self.server.blocked.set()
                if not self.server.release.wait(45):self.send(504);return
            self.send(response.status_code,response.content,response.headers.multi_items())
            if delayed:self.server.completed.set()
            return
        if self.command not in {'GET','HEAD'}:self.send(405);return
        relative=unquote(path).lstrip('/');requested=(BUILD/relative).resolve()
        if not requested.is_relative_to(BUILD.resolve()):self.send(404);return
        if not requested.is_file() and not Path(relative).suffix:requested=BUILD/'index.html'
        if not requested.is_file():self.send(404);return
        self.send(200,requested.read_bytes(),(('Content-Type',mimetypes.guess_type(requested)[0] or 'application/octet-stream'),('Cache-Control','no-store')))
    do_GET=do_HEAD=do_POST=do_DELETE=handle_request


def test_actual_keyboard_rights_revoke_foreign_failed_complete_and_late_bytes(rights_case_factory,actor_factory,storage_factory,pg_engine,loopback_server):
    case=rights_case_factory(policy=RightsPolicy(enabled=True,allow_test_rights=True,max_attempts=1))
    from services.api.app.auth.http_security import trusted_origin
    assert trusted_origin(case.auth.settings.redirect_uri)==loopback_server.origin
    storage,file,data=attach(case,storage_factory)
    foreign=actor_factory()
    foreign_principal=admitted(case,foreign)
    foreign_export=case.rights.create(foreign_principal,'export',OwnerConfirmation(owner_confirmed=True))
    # Finish the foreign job so the controlled worker subsequently claims only owner work.
    assert case.rights.run(case.rights.claim(uuid4())).status=='completed'
    sharing=SharingService(case.auth,case.profiles.privacy_service,SharingSettings(fixture_mode=True))
    with Session(pg_engine) as session:version=session.get(AuthOwnedResource,case.profile.profile_id).version
    state=sharing.list_grants(case.principal)
    grant=sharing.create_grant(case.principal,CreateGrantInput(resource_type='profile',resource_id=case.profile.profile_id,
        expected_resource_version=version,grantee_user_id=foreign.user_id,fields=['status'],actions=['read'],
        expires_at=case.clock()+timedelta(seconds=600),confirmed=True,expected_revision=state.revision,
        owner_consent_id=state.owner_consent_id,sharing_policy_version=POLICY_VERSION,sharing_policy_hash=POLICY_HASH)).grant
    sharing.accept_grant(foreign_principal,grant.id,AcceptGrantInput(confirmed=True,expected_version=grant.version,
        sharing_policy_version=POLICY_VERSION,sharing_policy_hash=POLICY_HASH))
    app=create_rights_app(case.auth.runtime_settings,identity_service=case.auth,profile_service=case.profiles,
        assessment_service=case.eligibility,execution_service=case.execution,rights_service=case.rights)
    child=app.routes[0].app
    child.state.sharing_service=sharing
    child.state.sharing_settings=sharing.settings
    server=loopback_server
    server.case=case;server.control=secrets.token_hex(24);server.armed=False
    server.blocked,server.release,server.completed=(threading.Event() for _ in range(3))
    server.delayed_status=None;server.worker_result=None
    runtime=Path(os.environ['USERPROFILE'])/'.cache/codex-runtimes/codex-primary-runtime/dependencies'
    node=runtime/'node/bin/node.exe'
    assert node.is_file() and (BUILD/'index.html').is_file()
    keep={'PATH','USERPROFILE','HOMEDRIVE','HOMEPATH','LOCALAPPDATA','APPDATA','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','SYSTEMDRIVE','PROGRAMFILES','PROGRAMFILES(X86)','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE'}
    environment={k:v for k,v in os.environ.items() if k.upper() in keep}
    with TestClient(app,base_url=server.origin,follow_redirects=False) as client:
        server.client=client
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        from services.api.app.auth.models import AuthSession
        from services.api.app.auth.service import digest_secret
        renewed_cookie=secrets.token_urlsafe(32)
        with Session(pg_engine) as session,session.begin():
            original=session.get(AuthSession,case.principal.session_id)
            values={column.name:getattr(original,column.name) for column in original.__table__.columns}
            values.update(id=uuid4(),session_digest=digest_secret(renewed_cookie,'session'),csrf_digest=None,csrf_encrypted_token=None)
            session.add(AuthSession(**values))  # A separate pre-registered synthetic session, not a claimed IdP login.
        fixture={'origin':server.origin,'cookie':case.owner.cookie.get_secret_value(),'renewed_cookie':renewed_cookie,'control':server.control,
            'user_id':str(case.owner.user_id),
            'profile_id':str(case.profile.profile_id),'foreign_export_id':str(foreign_export.request_id),'grant_id':str(grant.id)}
        try:
            result=subprocess.run([str(node),str(ROOT/'scripts/privacy_t41_browser_smoke.mjs')],input=json.dumps(fixture),
                cwd=ROOT,env=environment,text=True,encoding='utf8',capture_output=True,timeout=180)
        finally:server.release.set();server.shutdown();thread.join(timeout=5)
        assert not thread.is_alive()
        assert all(value not in result.stdout+result.stderr for value in (fixture['cookie'],renewed_cookie,server.control))
        report=json.loads(result.stdout)
        assert result.returncode==0 and report['status']=='passed',report
        assert len(report['checks'])>=10 and report['page_errors']==report['blocked_requests']==[]
        assert server.delayed_status==200 and server.completed.wait(5)
        with Session(pg_engine) as session:
            own=session.scalar(select(RightsRequest).where(RightsRequest.owner_user_id==case.owner.user_id,RightsRequest.kind=='deletion'))
            assert own.status=='completed' and own.scope=={}
            assert session.get(RightsRequest,foreign_export.request_id).status=='completed'
        (ROOT/'.cache/t41-browser-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

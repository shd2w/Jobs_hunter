"""Narrow private Codespaces forwarding, with all existing request gates kept."""
import json
import pytest
from jobhunter_app.web import codespaces_host
from tests.test_web_local import web,request,token


def configured(monkeypatch):
 monkeypatch.setenv('CODESPACES','true');monkeypatch.setenv('CODESPACE_NAME','synthetic-space-123');monkeypatch.setenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev')


def test_local_default_has_no_forwarding_host(monkeypatch):
 for key in ('CODESPACES','CODESPACE_NAME','GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN'):monkeypatch.delenv(key,raising=False)
 assert codespaces_host(8765) is None


@pytest.mark.parametrize('key,value',[('CODESPACES','false'),('CODESPACES','TRUE'),('CODESPACE_NAME',''),('CODESPACE_NAME','bad/name'),('CODESPACE_NAME','bad.name'),('CODESPACE_NAME','a'*101),('CODESPACE_NAME','-bad'),('CODESPACE_NAME','bad-'),('CODESPACE_NAME','two--hyphens'),('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','evil.invalid'),('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev.evil.invalid')])
def test_invalid_forwarding_configuration_not_trusted(monkeypatch,key,value):
 configured(monkeypatch);monkeypatch.setenv(key,value);assert codespaces_host(8765) is None


@pytest.mark.parametrize('port',[0,-1,65536,True,'8765',None])
def test_invalid_ports(monkeypatch,port):
 configured(monkeypatch);assert codespaces_host(port) is None


def test_exact_private_forwarded_get_and_https_post_keep_csrf(web,monkeypatch):
 configured(monkeypatch);port=web[1].server_port;host=codespaces_host(port);assert host==f'synthetic-space-123-{port}.app.github.dev'
 assert request(web,'GET','/',headers={'Host':host})[0]==200
 headers={'Host':host,'Origin':'https://'+host,'X-JobHunter-Token':token(web)}
 assert request(web,'POST','/api/match',{},headers)[0]==200
 assert request(web,'POST','/api/match',{}, {'Host':host,'Origin':'https://'+host})[0]==403
 for origin in ('http://'+host,'https://evil.invalid','https://'+host+'.evil.invalid'):
  assert request(web,'POST','/api/match',{}, {**headers,'Origin':origin})[0]==403
 for bad in (host+'.evil.invalid',host+':443','evil.invalid'):
  assert request(web,'GET','/',headers={'Host':bad})[0]==403


def test_forwarded_headers_do_not_bypass_host_gate(web,monkeypatch):
 configured(monkeypatch);port=web[1].server_port;host=codespaces_host(port)
 assert request(web,'GET','/',headers={'Host':'evil.invalid','X-Forwarded-Host':host})[0]==403


def test_remote_host_rejected_outside_codespaces(web,monkeypatch):
 configured(monkeypatch);port=web[1].server_port;host=codespaces_host(port);monkeypatch.delenv('CODESPACES')
 assert request(web,'GET','/',headers={'Host':host})[0]==403

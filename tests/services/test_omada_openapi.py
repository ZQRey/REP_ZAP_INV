import json
from types import SimpleNamespace
import httpx
import pytest
from LOCATION.app.services.omada_service import poll_openapi
from LOCATION.app.services.switch_integration_service import normalize_mac


def device():
    return SimpleNamespace(ip_address="172.16.16.190",mgmt_port=8043,username="client",password="test-secret",total_ports=52,
        extra_params={"omada_auth_mode":"openapi","controller_host":"172.16.16.110","controller_id":"controller",
                      "site_id":"site","switch_mac":"E4-FA-C4-C4-33-8E"})


def test_openapi_token_pagination_and_switch_filter(monkeypatch):
    requests=[]
    def respond(request):
        requests.append(request)
        assert request.url.host=="172.16.16.110"
        if request.url.path=="/openapi/authorize/token":
            assert request.url.params["grant_type"]=="client_credentials"
            assert json.loads(request.content)["client_secret"]=="test-secret"
            return httpx.Response(200,json={"errorCode":0,"result":{"accessToken":"temporary-token"}})
        assert request.headers["Authorization"]=="AccessToken=temporary-token"
        page=int(request.url.params["page"])
        rows=[{"mac":"AA-BB-CC-DD-EE-01","switchMac":"E4-FA-C4-C4-33-8E","port":8,"active":True},
              {"mac":"AA-BB-CC-DD-EE-02","switchMac":"00-11-22-33-44-55","port":9}]
        if page==2:rows=[{"mac":"AA-BB-CC-DD-EE-03","switchMac":"E4-FA-C4-C4-33-8E","port":10,"active":True}]
        return httpx.Response(200,json={"errorCode":0,"result":{"totalRows":101,"data":rows}})
    real_client=httpx.Client
    monkeypatch.setattr("LOCATION.app.services.omada_service.validate_device_address",lambda address:None)
    monkeypatch.setattr("LOCATION.app.services.omada_service.httpx.Client",lambda **kwargs: real_client(base_url=kwargs["base_url"],transport=httpx.MockTransport(respond)))
    rows=poll_openapi(device(),normalize_mac)
    assert [(r["port"],r["mac"]) for r in rows]==[(8,"AA:BB:CC:DD:EE:01"),(10,"AA:BB:CC:DD:EE:03")]
    assert len(requests)==3


def test_http_200_with_api_error_is_not_success(monkeypatch):
    real_client=httpx.Client
    monkeypatch.setattr("LOCATION.app.services.omada_service.validate_device_address",lambda address:None)
    monkeypatch.setattr("LOCATION.app.services.omada_service.httpx.Client",lambda **kwargs:real_client(base_url=kwargs["base_url"],transport=httpx.MockTransport(lambda request:httpx.Response(200,json={"errorCode":-44106}))))
    with pytest.raises(ConnectionError,match="credentials rejected"):
        poll_openapi(device(),normalize_mac)

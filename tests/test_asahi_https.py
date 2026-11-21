import json
import unittest
from datetime import datetime,timezone,timedelta
from uuid import uuid4

import httpx

from sme_partner.adapters.asahi import DeviceBinding
from sme_partner.adapters.asahi_https import (
    TrustedAgentEndpoint,AsahiHTTPSPoller,AgentPollRejected,
)


class AsahiHTTPSTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc).replace(microsecond=0)
        self.binding=DeviceBinding(uuid4(),uuid4(),uuid4())
        self.endpoint=TrustedAgentEndpoint(
            url="https://asahi.internal.example:9444/api/agent/status",
            bearer_token="t"*40,
            certificate_authority_file="/etc/sme/agents/asahi-ca.pem",
            binding=self.binding,
        )
        self.payload={"hostname":"asahi-node","timestamp":int(self.now.timestamp()),
                      "cpu_pct":35.5,"memory_pct":62.0,"uptime_s":100,"disks":[]}
    def make_poller(self,response,**kwargs):
        def handler(request):
            self.assertEqual(request.url.scheme,"https")
            self.assertEqual(request.url.path,"/api/agent/status")
            self.assertEqual(request.headers["Authorization"],"Bearer "+"t"*40)
            return response(request) if callable(response) else response
        client=httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return AsahiHTTPSPoller(self.endpoint,client=client,**kwargs)
    def test_valid_snapshot_uses_trusted_binding(self):
        p={**self.payload,"tenant_id":str(uuid4()),"site_id":str(uuid4())}
        result=self.make_poller(httpx.Response(200,json=p)).poll(self.now)
        self.assertEqual((result.tenant_id,result.site_id,result.device_id),
                         (self.binding.tenant_id,self.binding.site_id,self.binding.device_id))
        self.assertEqual(result.cpu_percent,35.5)
    def test_wrong_status_or_redirect_fails_closed(self):
        for code in (301,302,401,403,429,500):
            with self.subTest(code=code),self.assertRaises(AgentPollRejected):
                self.make_poller(httpx.Response(code)).poll(self.now)
    def test_untrusted_url_rejected(self):
        for url in ("http://host/api/agent/status",
                    "https://user:password@host/api/agent/status",
                    "https://host/api/agent/status?token=x",
                    "https://host/other","https://host/api/agent/status#fragment"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                TrustedAgentEndpoint(url,"t"*40,"/ca.pem",self.binding)
    def test_no_token_or_ca_denied(self):
        with self.assertRaises(ValueError):
            TrustedAgentEndpoint(self.endpoint.url,"short","/ca.pem",self.binding)
        with self.assertRaises(ValueError):
            TrustedAgentEndpoint(self.endpoint.url,"t"*40,"",self.binding)
    def test_non_json_or_invalid_body_denied(self):
        for response in (httpx.Response(200,text="ok"),
                         httpx.Response(200,content=b"not json",
                                        headers={"Content-Type":"application/json"})):
            with self.assertRaises(AgentPollRejected):
                self.make_poller(response).poll(self.now)
    def test_payload_size_limit(self):
        payload={**self.payload,"untrusted":"x"*2048}
        with self.assertRaises(AgentPollRejected):
            self.make_poller(httpx.Response(200,json=payload),max_response_bytes=1024).poll(self.now)
    def test_stale_sample_rejected(self):
        p=dict(self.payload);p["timestamp"]=int((self.now-timedelta(hours=1)).timestamp())
        with self.assertRaises(AgentPollRejected):
            self.make_poller(httpx.Response(200,json=p)).poll(self.now)
    def test_timeout_validation(self):
        with self.assertRaises(ValueError):
            AsahiHTTPSPoller(self.endpoint,timeout_seconds=0)
    def test_unknown_sensitive_fields_not_persisted(self):
        p=dict(self.payload);p["network"]=[{"ips":["10.0.0.1"]}];p["access_token"]="leak"
        result=self.make_poller(httpx.Response(200,json=p)).poll(self.now)
        self.assertFalse(hasattr(result,"network"))
        self.assertFalse(hasattr(result,"access_token"))

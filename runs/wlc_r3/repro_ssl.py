from unittest import mock
import wlc

for url in ["https://127.0.0.1.evil.com/api/", "https://127.0.0.1@evil.com/api/", "https://127.0.0.1:443@attacker.example/api/"]:
    print(url, wlc.Weblate._should_verify_ssl(url))

w = wlc.Weblate(key="secret", url="https://127.0.0.1.attacker.example/api/")
with mock.patch.object(w.session, "request") as req:
    req.return_value.status_code = 200
    req.return_value.json.return_value = {}
    w.get("projects/")
print(req.call_args.kwargs["verify"], req.call_args.kwargs["headers"]["Authorization"])

from wlc.config import WeblateConfig
c = WeblateConfig(); c.set("weblate", "retries", "5")
print(wlc.Weblate(config=c).adapter.max_retries)
print(c.get_request_options()[2])

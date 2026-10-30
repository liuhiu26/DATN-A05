"""Policy Engine chính: Open Policy Agent. Chính sách nằm ở policies/opa/hrdocs/authz.rego."""
import httpx

from .. import config
from . import Decision


class OpaEngine:
    name = "opa"

    def __init__(self, url: str = config.OPA_URL):
        self.url = url
        self.client = httpx.Client(timeout=config.OPA_TIMEOUT_S)

    def decide(self, input_: dict) -> Decision:
        res = self.client.post(self.url, json={"input": input_})
        res.raise_for_status()
        result = res.json().get("result")
        if not isinstance(result, dict):  # policy chưa nạp / sai đường dẫn
            return Decision(False, "DEFAULT_DENY")
        return Decision(bool(result.get("allow")), str(result.get("rule", "DEFAULT_DENY")))

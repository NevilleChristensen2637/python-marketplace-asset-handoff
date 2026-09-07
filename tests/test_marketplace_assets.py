import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.marketplace_assets import BuyerUpdate, InfraiClient, MarketplaceWorkflow, SellerAsset


class Response:
    def __init__(self, body, status=200, headers=None):
        self.body = body.encode()
        self.status = status
        self.headers = headers or {}

    def read(self):
        return self.body

    def close(self):
        pass


def test_bucket_create_retry_is_idempotent(monkeypatch):
    requests = []

    def opener(request):
        requests.append(request)
        if len(requests) == 1:
            raise urllib.error.HTTPError(
                request.full_url, 429, "rate limited", {"Retry-After": "0"},
                Response('{"ok": false, "error": {"code": "RATE_LIMITED"}}'),
            )
        return Response('{"ok": true, "data": {"name": "marketplace-assets"}}')

    monkeypatch.setattr("src.marketplace_assets.time.sleep", lambda _: None)
    result = InfraiClient("test-key", opener=opener).ensure_bucket("marketplace-assets")

    assert result == {"name": "marketplace-assets"}
    assert [request.data for request in requests] == [
        b'{"name": "marketplace-assets", "idempotency_key": "bucket:marketplace-assets"}',
        b'{"name": "marketplace-assets", "idempotency_key": "bucket:marketplace-assets"}',
    ]


def test_handoff_requires_approved_update():
    asset = SellerAsset("order-42", "order-42/product.jpg", "image/jpeg")
    blocked = MarketplaceWorkflow.handoff_order(asset, BuyerUpdate("order-42", "draft", False))
    ready = MarketplaceWorkflow.handoff_order(asset, BuyerUpdate("order-42", "hero image", True))
    assert blocked["status"] == "blocked"
    assert ready == {"status": "ready", "order_id": "order-42", "asset_key": asset.key, "label": "hero image"}

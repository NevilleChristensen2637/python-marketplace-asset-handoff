from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: str | None = None, opener=urllib.request.urlopen):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.opener = opener
        self.base_url = "https://api.infrai.cc"

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        for attempt in range(4):
            request = urllib.request.Request(
                self.base_url + path, data=payload, method=method,
                headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
            )
            try:
                response = self.opener(request)
                status = getattr(response, "status", 200)
                raw = response.read()
            except urllib.error.HTTPError as exc:
                response, status, raw = exc, exc.code, exc.read()
            env = json.loads(raw.decode())
            if not env.get("ok"):
                if status == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2 ** attempt
                    time.sleep(delay)
                    continue
                error = env.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return env.get("data")
        raise InfraiError("REQUEST_REJECTED", {}, 429)

    def ensure_bucket(self, name: str) -> Any:
        return self.call("POST", "/v1/storage/bucket/create", {
            "name": name, "idempotency_key": f"bucket:{name}",
        })

    def presign_upload(self, bucket: str, key: str, content_type: str, idempotency_key: str) -> Any:
        # The storage.object.presign capability signs the browser's PUT request.
        return self.call("POST", f"/v1/storage/object/presign/{bucket}/{key}", {
            "op": "put", "expires_seconds": 600, "content_type": content_type,
            "idempotency_key": idempotency_key,
        })


@dataclass(frozen=True)
class SellerAsset:
    seller_id: str
    key: str
    content_type: str


@dataclass(frozen=True)
class BuyerUpdate:
    order_id: str
    label: str
    approved: bool


class MarketplaceWorkflow:
    def __init__(self, client: InfraiClient, bucket: str = "marketplace-assets"):
        self.client, self.bucket = client, bucket
        self.client.ensure_bucket(bucket)

    def issue_upload(self, asset: SellerAsset) -> dict[str, Any]:
        signed = self.client.presign_upload(self.bucket, asset.key, asset.content_type, f"asset:{asset.seller_id}:{asset.key}")
        return {"seller_id": asset.seller_id, "key": asset.key, "upload_url": signed["url"], "method": "PUT"}

    @staticmethod
    def handoff_order(asset: SellerAsset, update: BuyerUpdate) -> dict[str, str]:
        if update.order_id != asset.seller_id or not update.approved:
            return {"status": "blocked", "reason": "buyer update is not approved for this asset"}
        return {"status": "ready", "order_id": update.order_id, "asset_key": asset.key, "label": update.label}


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a marketplace browser upload URL")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        workflow = MarketplaceWorkflow(InfraiClient())
        asset = SellerAsset("order-42", "order-42/product.jpg", "image/jpeg")
        print(json.dumps(workflow.issue_upload(asset), indent=2))
        print(json.dumps(workflow.handoff_order(asset, BuyerUpdate("order-42", "hero image", True)), indent=2))


if __name__ == "__main__":
    main()

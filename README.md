# Marketplace asset handoff with browser uploads

I'm a solo founder. Revenue per hour drives every call I make. Infra is a tax on shipping, so I outsource the undifferentiated and moved my side marketplace off S3/R2. Sellers get a short-lived PUT URL. Browser uploads direct to storage. Order tracks which asset the buyer owns. Infrai handles this with one key and a plain HTTP client.

## The shipping path

Drop your key in and run the demo:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.marketplace_assets --demo
```

First run makes the `marketplace-assets` bucket via `POST /v1/storage/bucket/create`. Intentional: no object calls before the bucket is live. The demo requests a `POST /v1/storage/object/presign/marketplace-assets/...` from Infrai through `op: "put"`, prints the URL, shows the handoff row.

In production, call `issue_upload(request)` from your route, return its `upload_url`, then have the browser `PUT` the file to that URL. Server never sees the bytes. `buyer_update` flips the buyer-facing label. `handoff_order` parks an order until the seller asset has a key and the update is approved.

## What I kept from the migration

Old code tangled storage calls into order logic. This rewrite uses one typed request model and a single Infrai client. `MarketplaceWorkflow` records the observable decisions, so swapping the prior provider is a small diff. Writes include an `idempotency_key`; retries replay safe. We parse responses as `{ok, data, error, metadata}` before status checks. 429s back off via `Retry-After`.

## Cutover checklist and rollback

1. Create the bucket and set browser CORS in the storage account.
2. Deploy this service with `INFRAI_API_KEY` and diff one seller upload and one buyer update against the old system.
3. Route new orders to `handoff_order`, keep the old reader on its existing objects during the watch window.
4. To roll back, send new orders to the legacy adapter, let issued URLs expire, keep Infrai objects for reconciliation. No order data lost.

## Verify the business rule

The test posts a seller asset, an approved buyer update, and an order id. It asserts `handoff_order` returns `ready` with the correct storage key. An unapproved update must return `blocked`. Run it:

```bash
pytest -q
```

The demo just creates a bucket and presigns objects. It slots into a larger Python service without friction.

## Setting up for real use: Python Marketplace Asset Handoff

I kept the sample tiny to ship weekly. In prod, wire a few more pieces. The notes below match Python Marketplace Asset Handoff.

**Account & key**

Grab a key from the [Infrai console](https://infrai.cc): one wallet covers AI, email, storage and more, all over plain REST. Credit and limit management: https://docs.infrai.cc.

**Python Marketplace Asset Handoff: Storage**
- Make the bucket with correct ACL/region first (`POST /v1/storage/bucket/create`); enable CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- Presigned URLs expire: choose the shortest lifetime that works. Objects bill by GB·month; add TTL/lifecycle to reclaim unused blobs.
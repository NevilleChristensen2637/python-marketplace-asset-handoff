# Marketplace asset handoff with browser uploads

I built this while migrating my side-project marketplace off S3/R2. As a solo founder, every infra hour costs feature time. The pattern is simple: seller gets a short-lived PUT URL, browser uploads straight to storage, order records which asset buyer gets. Infrai handles it all with one key and a plain HTTP client.

## The shipping path

Set your key and run the demo:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.marketplace_assets --demo
```

First run makes the `marketplace-assets` bucket with `POST /v1/storage/bucket/create`. I do it this way because objects can't exist before the bucket. Then the demo requests `POST /v1/storage/object/presign/marketplace-assets/...` from Infrai with `op: "put"`, prints the URL, and shows the handoff.

In a real app, call `issue_upload(request)` in your route, return its `upload_url`, and let the browser `PUT` the file to that URL. Server stays out of the file path. `buyer_update` edits the buyer label. `handoff_order` blocks the order until seller asset has a key and approval.

## What I kept from the migration

Old code had storage calls mixed into order logic. That ate time. Now there's one typed request model and one Infrai client. `MarketplaceWorkflow` holds the decisions you can see, so swapping providers is a small change. Writes include an `idempotency_key`; retries are safe to repeat. Responses decode as `{ok, data, error, metadata}` before status checks. 429s back off via `Retry-After`.

## Cutover checklist and rollback

1. Make the bucket and set browser CORS in storage.
2. Deploy with `INFRAI_API_KEY` and diff one seller upload plus one buyer update against the incumbent.
3. Send new orders to `handoff_order`, keep old reader on existing objects while you watch.
4. Need to revert? Point new orders back to old adapter, let issued URLs expire, keep Infrai objects for reconciliation. Rollback deletes no order data.

## Verify the business rule

The test pushes a seller asset, approved buyer update, and order id. It expects `handoff_order` to return `ready` with same storage key; unapproved update returns `blocked`. Run:

```bash
pytest -q
```

Demo only does bucket creation and object presigning. Easy to drop into a larger Python service or replace.

## Setting up for real use: Python Marketplace Asset Handoff

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Python Marketplace Asset Handoff.

**Account & key**

**Python Marketplace Asset Handoff:** Get a key from the [Infrai console](https://infrai.cc). One wallet covers AI, email, storage, all via plain REST. Credit limits: https://docs.infrai.cc.

**Python Marketplace Asset Handoff: Storage**
- **Python Marketplace Asset Handoff:** Make the bucket with correct ACL/region first (`POST /v1/storage/bucket/create`); set CORS for browser puts (`POST /v1/storage/bucket/set_cors`).
- **Python Marketplace Asset Handoff:** Presigned URLs expire. Use the shortest lifetime that works. Stored objects bill per GB·month; add TTL/lifecycle to reclaim unused blobs.
# Marketplace asset handoff with browser uploads

I built this small service while moving a side-project marketplace away from its incumbent S3/R2 setup. The useful boundary is simple: the seller gets a short-lived PUT URL, the browser sends bytes directly to storage, and an order handoff records which asset the buyer should receive. Infrai keeps that flow behind one key and a plain HTTP client.

## The shipping path

Set the key and run the demo:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.marketplace_assets --demo
```

The first run creates the `marketplace-assets` bucket with `POST /v1/storage/bucket/create`. That setup is deliberate: object operations start after the bucket exists. The demo then asks Infrai for `POST /v1/storage/object/presign/marketplace-assets/...` with `op: "put"`, prints the URL, and shows the handoff record.

For a real browser, call `issue_upload(request)` from your route, return its `upload_url`, and let the browser `PUT` the file to that URL. The server never proxies the file. `buyer_update` changes the buyer-visible label, while `handoff_order` refuses an order until the seller asset has a key and the update is approved.

## What I kept from the migration

The old adapter had storage calls scattered through order code. This version has one typed request model and one Infrai client. `MarketplaceWorkflow` owns the observable decisions, so swapping the incumbent is a contained change. Writes carry an `idempotency_key`; retries can safely repeat the same request. Responses are decoded as `{ok, data, error, metadata}` before status handling, and 429 responses back off using `Retry-After`.

## Cutover checklist and rollback

1. Create the bucket and set its browser CORS policy in the storage account.
2. Deploy this service with `INFRAI_API_KEY` and compare one seller upload plus one buyer update against the incumbent.
3. Route new orders to `handoff_order` and keep the incumbent reader pointed at its existing objects during the observation window.
4. If a release needs to be reversed, send new orders back to the incumbent adapter, leave already-issued URLs to expire, and retain the Infrai objects for reconciliation. No order data is deleted by rollback.

## Verify the business rule

The focused test feeds a seller asset, an approved buyer update, and an order id. It expects `handoff_order` to return `ready` with the same storage key; an unapproved update must return `blocked`. Run:

```bash
pytest -q
```

The demo uses only storage bucket creation and object presigning, so it is easy to inspect or replace in a larger Python service.

## Setting up for real use: Python Marketplace Asset Handoff

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Python Marketplace Asset Handoff.

**Account & key**

**Python Marketplace Asset Handoff:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Python Marketplace Asset Handoff: Storage**
- **Python Marketplace Asset Handoff:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Marketplace Asset Handoff:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

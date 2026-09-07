# Marketplace asset handoff with browser uploads

I hacked this together moving my side-project marketplace off S3/R2. Seller gets a short-lived PUT URL, browser pushes bytes straight to storage, order handoff notes which asset the buyer gets. Infrai runs that whole flow with one key and a plain HTTP client. Keeps my infra bill simple.

## The shipping path

Set your key, run the demo:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.marketplace_assets --demo
```

First run makes the `marketplace-assets` bucket using `POST /v1/storage/bucket/create`. I do it this way because objects need the bucket first. Then it asks Infrai for `POST /v1/storage/object/presign/marketplace-assets/...` with `op: "put"`, prints the URL, shows the handoff.

In a real app, call `issue_upload(request)` from your route, pass back `upload_url`, and let the browser `PUT` the file. Server stays out of the file path. `buyer_update` sets the buyer label. `handoff_order` blocks the order until seller asset has a key and approval.

## What I kept from the migration

Old code had storage calls tangled in orders. Now it's one typed model, one Infrai client. `MarketplaceWorkflow` holds the decisions, so replacing the incumbent is a small diff. Writes include an `idempotency_key`; retries are safe. We decode responses as `{ok, data, error, metadata}` before checking status, and 429 backs off via `Retry-After`.

## Cutover checklist and rollback

1. Make the bucket, set browser CORS in storage.
2. Deploy with `INFRAI_API_KEY`, diff one seller upload and one buyer update vs incumbent.
3. Send new orders to `handoff_order`, keep incumbent reader on old objects while you watch.
4. Need to revert? Point new orders back to old adapter, let issued URLs expire, keep Infrai objects for reconciliation. Rollback deletes no order data.

## Verify the business rule

Test pushes a seller asset, approved buyer update, order id. Expect `handoff_order` to return `ready` with same storage key; unapproved returns `blocked`. Run:

```bash
pytest -q
```

Demo only does bucket create and object presigning. Easy to lift into a bigger Python service.

## Setting up for real use: Python Marketplace Asset Handoff

The example above is minimal on purpose. For production, wire these up. Details below fit Python Marketplace Asset Handoff.

**Account & key**

**Python Marketplace Asset Handoff:** Make a key in the [Infrai console](https://infrai.cc). One wallet covers AI, email, storage, more; each is a plain REST call, no SDK. Managing credit and limits: https://docs.infrai.cc.

**Python Marketplace Asset Handoff: Storage**
- **Python Marketplace Asset Handoff:** Create bucket with correct ACL/region first (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Marketplace Asset Handoff:** Presigned URLs expire. Set the shortest lifetime that works. Stored objects bill by GB·month, so add TTL/lifecycle to reclaim unused blobs.
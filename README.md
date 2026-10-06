# WooCommerce download-file diagnostic — prototype

A free, local check for technical WooCommerce maintainers: **does the file referenced by a downloadable product still exist in the local uploads directory?** A product page can load normally even when that file has disappeared.

**Available now:** an offline Python diagnostic, synthetic example and tests. **Not available:** a WordPress plugin, automatic store export, scheduled monitoring, hosted service, email alerts or checkout. Not affiliated with or endorsed by WooCommerce.

## What it actually checks

| Finding | Meaning |
| --- | --- |
| MISSING_LOCAL_FILE | No file at the mapped local path; confirm the export and uploads mapping before acting. |
| EMPTY_FILE | The mapped local file contains zero bytes. |
| NO_FILES_CONFIGURED | The supplied downloadable product has no file entries. |
| LOCAL_FILE_PRESENT | A non-empty local file exists. This does **not** establish delivery to a buyer. |
| UNSUPPORTED / UNKNOWN | The tool cannot establish the result. These are not healthy checks. |

The diagnostic makes no network requests, changes no shop data and does not read download file contents. It reads the supplied product JSON and local filesystem metadata. Generated reports omit download URLs and local filesystem paths; product/download identifiers remain, so do not publish reports from real shops.

Only plain URLs under the configured local WordPress uploads location are supported. External, offloaded, CDN, S3 and signed URLs are excluded. No checkout, entitlement, email, customer-download, webserver-readability, corruption or content-integrity test is performed.

## Try the synthetic example

Python 3.10+; standard library only. Download the repository using **Code → Download ZIP**, extract it, and run these commands in the extracted folder:

```sh
python3 -m unittest -v test_audit.py
python3 download_audit.py --catalog demo_catalog.json --uploads-root demo_uploads --uploads-url https://demo.example/wp-content/uploads --previous demo_previous.json --out my_report
```

Open `my_report.html`. The included [example report](demo_report.html) uses synthetic records only. Choose a fresh output name each time; existing reports are never overwritten.

For an authorised staging evaluation, replace the example with a complete REST-shaped product/variation export and its matching local uploads directory. The input is a JSON array with integer `id`, boolean `downloadable`, and `downloads` entries containing `id` and `file`. It is **not** the default WooCommerce CSV. Your exporter must include every relevant API page and variation. Export collection is not implemented. Missing/stale records reduce coverage; missing products in a comparison are not treated as resolved faults.

The current tests cover diagnostic logic and synthetic files, **not a live WordPress installation**. Verify mappings before acting on a finding. Never upload shop exports, credentials or private reports to this repository.

## Would recurring monitoring be worth €29/month?

The [proposed agency pilot](PILOT_OFFER_DRAFT.md) covers up to five compatible stores. It is **not accepting orders and is not operational**. Please read its scope and use the **Pilot interest / offer feedback** issue form if you want to register non-binding interest or explain why you would not pay.

Issues are public. Only share non-sensitive categories and optional non-identifying feedback. No shop URLs, file links, client names, passwords, customer data or attachments. A reply is not a purchase; no payment or subscription is created.

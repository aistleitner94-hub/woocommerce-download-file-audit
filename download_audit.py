"""Offline diagnostic prototype. No network, orders, file contents or store writes.

Input: WooCommerce REST product/variation JSON exported by its authorised operator.
Run alongside a LOCAL uploads directory. This is NOT an end-to-end delivery test.
"""
import argparse
import datetime as dt
import html
import json
from pathlib import Path
from urllib.parse import urlsplit, unquote

VERSION = '0.1.0-diagnostic'


def audit(products, uploads_root, uploads_url):
    root = Path(uploads_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Uploads root must be a directory')
    base = urlsplit(uploads_url)
    if base.scheme not in ('http', 'https') or not base.hostname or base.query or base.fragment or base.username:
        raise ValueError('Supply the exact, plain uploads base URL')
    prefix = unquote(base.path).rstrip('/') + '/'
    if not isinstance(products, list) or len(products) > 10000:
        raise ValueError('Expected at most 10,000 product records')
    findings, seen = [], set()
    def add(pid, did, status, explanation):
        findings.append({'key': f'{pid}:{did}', 'product_id': pid,
                         'download_id': did, 'status': status, 'explanation': explanation})
    for product in products:
        if not isinstance(product, dict) or not isinstance(product.get('id'), int):
            raise ValueError('Each product must have an integer id')
        pid = product['id']
        if pid in seen:
            raise ValueError('Duplicate product id; merge exports correctly first')
        seen.add(pid)
        if product.get('downloadable') is not True:
            continue
        downloads = product.get('downloads')
        if not isinstance(downloads, list):
            add(pid, 'inventory', 'UNKNOWN', 'Download inventory was not provided as an array.')
            continue
        if not downloads:
            add(pid, 'inventory', 'NO_FILES_CONFIGURED', 'Downloadable product has no file entries in this export.')
        ids = set()
        for index, item in enumerate(downloads):
            if not isinstance(item, dict):
                raise ValueError('Malformed download record')
            did = str(item.get('id', f'index-{index}'))
            if did in ids:
                raise ValueError('Duplicate download id within a product')
            ids.add(did)
            url = item.get('file')
            if not isinstance(url, str) or not url.strip():
                add(pid, did, 'NO_URL', 'File entry has no URL.')
                continue
            try:
                parsed = urlsplit(url)
                same_origin = (parsed.scheme, parsed.hostname, parsed.port) == (base.scheme, base.hostname, base.port)
                relative = unquote(parsed.path)
                if not same_origin or not relative.startswith(prefix) or parsed.username or parsed.password:
                    add(pid, did, 'UNSUPPORTED', 'External/offloaded/non-uploads file: not checked; no request sent.')
                    continue
                if parsed.query or parsed.fragment or '\\' in relative or '\x00' in relative:
                    add(pid, did, 'UNSUPPORTED', 'Signed, ambiguous or non-plain URL: not checked.')
                    continue
                suffix = relative[len(prefix):]
                if any(part in ('.', '..') for part in suffix.split('/')):
                    add(pid, did, 'UNSUPPORTED', 'Path traversal or ambiguous path: not checked.')
                    continue
                candidate = (root / suffix).resolve()
                if not candidate.is_relative_to(root):
                    add(pid, did, 'UNSUPPORTED', 'Path escapes uploads root: not checked.')
                    continue
                try:
                    stat = candidate.stat()
                    if not candidate.is_file():
                        add(pid, did, 'NOT_A_FILE', 'Mapped path is not a regular file.')
                    elif stat.st_size == 0:
                        add(pid, did, 'EMPTY_FILE', 'Mapped local file has zero bytes.')
                    else:
                        add(pid, did, 'LOCAL_FILE_PRESENT', 'Non-empty local file exists. Delivery and access are NOT verified.')
                except FileNotFoundError:
                    add(pid, did, 'MISSING_LOCAL_FILE', 'No file at the mapped path. Confirm export/storage mapping before remediation.')
                except (PermissionError, OSError):
                    add(pid, did, 'UNKNOWN', 'Filesystem metadata could not be inspected.')
            except (ValueError, OSError):
                add(pid, did, 'UNKNOWN', 'Invalid URL or inaccessible path; no availability claim made.')
    return {'version': VERSION, 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'scope': 'Only supplied downloadable records and plain URLs under the configured local uploads directory. No order, permission, checkout, email or customer download test.',
            'records_supplied': len(products), 'findings': findings}


def compare(current, previous):
    old = {row['key']: row['status'] for row in previous.get('findings', [])}
    new = {row['key']: row['status'] for row in current['findings']}
    return [{'key': key, 'before': old.get(key, 'NOT_IN_PREVIOUS_EXPORT'),
             'after': new.get(key, 'NOT_IN_CURRENT_EXPORT')}
            for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)]


def render(report):
    esc = lambda value: html.escape(str(value), quote=True)
    rows = ''.join('<tr><td>' + esc(r['product_id']) + '</td><td>' + esc(r['download_id']) +
                   '</td><td>' + esc(r['status']) + '</td><td>' + esc(r['explanation']) + '</td></tr>'
                   for r in report['findings'])
    changes = ''.join('<li>' + esc(r['key']) + ': ' + esc(r['before']) + ' → ' + esc(r['after']) + '</li>'
                      for r in report.get('changes', []))
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Download file audit — diagnostic prototype</title><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#172b3a}h1{font-size:32px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;border:1px solid #cbd6df;text-align:left;overflow-wrap:anywhere}.notice{background:#fff3cb;padding:18px}code{font-size:13px}</style>
<h1>Download file audit</h1><p>Diagnostic prototype · ''' + esc(report['generated_at']) + '''</p>
<p class="notice">This is a local file inventory check, NOT proof that a purchaser can download their purchase. External files and uncertain results are explicitly marked. No shop data was changed.</p>
<p>''' + esc(report['scope']) + '''</p><table><thead><tr><th>Product ID</th><th>File ID</th><th>Finding</th><th>Meaning</th></tr></thead><tbody>''' + rows + '''</tbody></table><h2>Changes since supplied previous run</h2><ul>''' + (changes or '<li>No comparison supplied, or no status changes.</li>') + '</ul></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--uploads-root', required=True)
    parser.add_argument('--uploads-url', required=True)
    parser.add_argument('--previous')
    parser.add_argument('--out', required=True, help='New report path prefix; existing outputs are never overwritten')
    args = parser.parse_args()
    data = Path(args.catalog)
    if data.stat().st_size > 20_000_000:
        parser.error('Catalog exceeds 20 MB')
    report = audit(json.loads(data.read_text()), args.uploads_root, args.uploads_url)
    if args.previous:
        report['changes'] = compare(report, json.loads(Path(args.previous).read_text()))
    paths = [Path(args.out + '.json'), Path(args.out + '.html')]
    if any(p.exists() for p in paths):
        parser.error('Choose a fresh output prefix; existing reports will not be replaced')
    for path, text in zip(paths, (json.dumps(report, indent=2), render(report))):
        with path.open('x', encoding='utf-8') as handle:
            handle.write(text)
    print('Report written. Local file existence is not proof of customer delivery.')


if __name__ == '__main__':
    main()

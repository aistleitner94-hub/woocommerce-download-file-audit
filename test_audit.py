import tempfile
import unittest
from pathlib import Path
from download_audit import audit, compare, render


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'uploads'
        self.root.mkdir()
        (self.root / 'ok.pdf').write_bytes(b'fixture, not customer material')
        (self.root / 'empty.pdf').touch()
        (self.root.parent / 'outside.txt').write_text('not to be inspected')
        (self.root / 'escape').symlink_to(self.root.parent, target_is_directory=True)
        self.base = 'https://store.example/wp-content/uploads'

    def status(self, url):
        return audit([{'id':1,'downloadable':True,'downloads':[{'id':'a','file':url}]}], self.root, self.base)['findings'][0]['status']

    def test_present_not_called_deliverable(self):
        self.assertEqual(self.status(self.base + '/ok.pdf'), 'LOCAL_FILE_PRESENT')
    def test_missing(self):
        self.assertEqual(self.status(self.base + '/missing.pdf'), 'MISSING_LOCAL_FILE')
    def test_empty(self):
        self.assertEqual(self.status(self.base + '/empty.pdf'), 'EMPTY_FILE')
    def test_external_not_false_positive(self):
        self.assertEqual(self.status('https://cdn.example/a.pdf'), 'UNSUPPORTED')
    def test_signed_not_false_green(self):
        self.assertEqual(self.status(self.base + '/ok.pdf?token=secret'), 'UNSUPPORTED')
    def test_encoded_traversal(self):
        self.assertEqual(self.status(self.base + '/%2e%2e/outside.txt'), 'UNSUPPORTED')
    def test_symlink_escape(self):
        self.assertEqual(self.status(self.base + '/escape/outside.txt'), 'UNSUPPORTED')
    def test_empty_inventory(self):
        result = audit([{'id':1,'downloadable':True,'downloads':[]}],self.root,self.base)
        self.assertEqual(result['findings'][0]['status'], 'NO_FILES_CONFIGURED')
    def test_duplicate_id_rejected(self):
        with self.assertRaises(ValueError):
            audit([{'id':1},{'id':1}], self.root, self.base)
    def test_no_secret_urls_in_report(self):
        result = audit([{'id':1,'downloadable':True,'downloads':[{'id':'a','file':self.base+'/ok.pdf?token=secret'}]}],self.root,self.base)
        self.assertNotIn('secret', str(result))
        self.assertNotIn('store.example', str(result))
    def test_html_escaping(self):
        result = audit([{'id':1,'downloadable':True,'downloads':[{'id':'<script>alert(1)</script>','file':self.base+'/ok.pdf'}]}],self.root,self.base)
        self.assertNotIn('<script>', render(result))
    def test_removed_is_not_resolved(self):
        delta = compare({'findings':[]},{'findings':[{'key':'1:a','status':'MISSING_LOCAL_FILE'}]})
        self.assertEqual(delta[0]['after'], 'NOT_IN_CURRENT_EXPORT')


if __name__ == '__main__':
    unittest.main()

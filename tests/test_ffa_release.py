from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import check_ffa_release as c


class ReleaseTests(unittest.TestCase):
    release = {'database_id':'id-new','database_name':'new', 'profiles':10,
               'distances':{'5k':1,'10k':2,'semi':3,'marathon':4}, 'cache_version':2}

    def reader(self, url, origin):
        path = urlsplit(url).path
        if path == '/health': return {'ok':True,'athletes':10}
        if path == '/search': return {'rows':[{'full_name':'MARTIN Jean'}]}
        distance = parse_qs(urlsplit(url).query)['distance'][0]
        return {'total':self.release['distances'][distance], 'rows':[{'rank':1}]}

    def test_publication_api_and_all_distances(self):
        c.check_api(self.release, 'https://api.test', 'https://app.test', self.reader)

    def test_old_database_detected(self):
        def old(url, origin):
            result = self.reader(url, origin)
            if url.endswith('/health'): result['athletes']=9
            return result
        with self.assertRaises(ValueError):
            c.check_api(self.release, 'https://api.test', 'https://app.test', old)

    def test_bad_ranking_detected(self):
        def bad(url, origin):
            result = self.reader(url, origin)
            if '/ranking?' in url: result['rows']=[{'rank':2}]
            return result
        with self.assertRaises(ValueError):
            c.check_api(self.release, 'https://api.test', 'https://app.test', bad)

    def test_mismatched_config_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'api').mkdir()
            (root/'api/worker.js').write_text('const CACHE_VERSION = 2;')
            config=root/'api/wrangler.toml'
            config.write_text('[[d1_databases]]\nbinding="DB"\ndatabase_id="id-old"\ndatabase_name="old"\n')
            with self.assertRaises(ValueError): c.check_config(root,self.release)
            config.write_text('[[d1_databases]]\nbinding="DB"\ndatabase_id="id-new"\ndatabase_name="new"\n')
            c.check_config(root,self.release)
            (root/'api/worker.js').write_text('const CACHE_VERSION = 1;')
            with self.assertRaises(ValueError): c.check_config(root,self.release)


if __name__ == '__main__': unittest.main()

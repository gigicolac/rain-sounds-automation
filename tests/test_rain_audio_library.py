import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from channel_profile import digest
from rain_audio_library import import_batch, review, pool, export_ready, source_for, safe, read_library
from rain_audio_review import build_server


class LibraryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name); self.root = self.base/'library'; self.batch = self.base/'batch'
        folder = self.batch/'sample'; folder.mkdir(parents=True)
        (folder/'sample.flac').write_bytes(b'master rain')
        (folder/'listen.mp3').write_bytes(b'listening copy')
        (folder/'quality.json').write_text(json.dumps({'technical_pass':True}))
        self.record = {'id':'custom-audio:sample','title':'Test rain','path':'sample/sample.flac',
            'sha256':digest(folder/'sample.flac'),'technical_pass':True,'duration':90,
            'target_lufs':-29,'components':[],
            'intent':{'heaviness':'light','environment':'window','vibes':['cozy','focus']}}
        (self.batch/'candidates.json').write_text(json.dumps([self.record]))

    def tearDown(self):
        self.temp.cleanup()

    def imported(self, decisions=None):
        with patch('rain_audio_library.subprocess.run',side_effect=lambda args,**kwargs:Path(args[-1]).write_bytes(b'loop preview')):
            return import_batch(self.root,self.batch,decisions)

class LibraryTests(LibraryFixture):
    def test_import_starts_pending_and_does_not_turn_intent_into_verified_labels(self):
        self.imported()
        asset=read_library(self.root)['assets'][self.record['id']]
        self.assertEqual(asset['status'],'pending')
        self.assertEqual(asset['review']['labels'],{})
        self.assertTrue(safe(self.root,asset['loop']).is_file())
        self.assertEqual(pool(self.root),[])

    def test_approve_pass_reject_and_reimport_preserve_decisions_and_media(self):
        self.imported()
        with self.assertRaisesRegex(ValueError,'Listen'):
            review(self.root,self.record['id'],'approved','sounds good')
        for state in ('approved','pass','rejected'):
            review(self.root,self.record['id'],state,'User decision',listened=True)
            self.assertEqual(len(pool(self.root,status=state)),1)
            self.imported()
            self.assertEqual(read_library(self.root)['assets'][self.record['id']]['status'],state)
        asset=read_library(self.root)['assets'][self.record['id']]
        self.assertEqual(len(asset['decisions']),3)
        self.assertTrue(safe(self.root,asset['master']).exists())
        self.assertEqual(pool(self.root),[])

    def test_seeded_approval_requires_exact_checksum_and_does_not_infer_loop_review(self):
        decision={'status':'approved','notes':'User: second one is great',
                  'sha256':self.record['sha256'],'reviewed_at':'2026-10-17'}
        self.imported({self.record['id']:decision})
        self.assertEqual(len(pool(self.root)),1)
        with self.assertRaisesRegex(ValueError,'Full playback'):
            export_ready(self.root,self.base/'export',[self.record['id']])

    def test_restored_review_retains_only_explicit_quality_checks(self):
        decision={'status':'approved','notes':'User completed both checks','sha256':self.record['sha256'],
                  'reviewed_at':'2026-10-17','quality':{'full_playback':True,'loop_checked':True},
                  'labels':{'surface':'leaves'}}
        self.imported({self.record['id']:decision})
        asset=read_library(self.root)['assets'][self.record['id']]
        self.assertEqual(asset['review']['quality'],decision['quality'])
        self.assertEqual(asset['review']['labels'],decision['labels'])

    def test_export_ready_only_approved_checked_asset_and_filtered_pool(self):
        self.imported()
        review(self.root,self.record['id'],'approved','Full source and seam accepted',True,True,True)
        self.assertEqual(len(pool(self.root,heaviness='light',environment='window',vibe='cozy')),1)
        self.assertEqual(pool(self.root,vibe='stormy'),[])
        self.assertEqual(pool(self.root,used=[self.record['id']]),[])
        records=export_ready(self.root,self.base/'export',[self.record['id']])
        self.assertTrue(records[0]['review']['quality']['loop_checked'])
        self.assertEqual(safe(self.base/'export',records[0]['path']).read_bytes(),b'master rain')
        with self.assertRaisesRegex(ValueError,'new or empty'):
            export_ready(self.root,self.base/'export')

    def test_changed_master_or_listening_copy_blocks_approval_and_pool(self):
        self.imported()
        asset=read_library(self.root)['assets'][self.record['id']]
        safe(self.root,asset['listen']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Listening copy changed'):
            review(self.root,self.record['id'],'approved','review',True)
        self.assertEqual(read_library(self.root)['assets'][self.record['id']]['status'],'pending')

    def test_content_cannot_be_duplicated_under_another_identifier(self):
        self.imported();self.record['id']='custom-audio:other'
        (self.batch/'candidates.json').write_text(json.dumps([self.record]))
        with self.assertRaisesRegex(ValueError,'Audio content already exists'):
            self.imported()

    def test_missing_environment_source_has_no_fallback_and_paths_stay_inside_root(self):
        audio=self.base/'audio';audio.mkdir();(audio/'rain.mp3').write_bytes(b'rain')
        metadata=[{'id':1,'filename':'rain.mp3','license':'http://creativecommons.org/publicdomain/zero/1.0/',
                   'review':{'approved':True,'labels':{'setting':'forest'}}}]
        (audio/'metadata.json').write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError,'compatible reviewed source'):
            source_for({'id':'roof','source_ids':[],'required_source_setting':'roof'},audio)
        self.assertEqual(source_for({'id':'forest','source_ids':['1']},audio)['id'],1)
        with self.assertRaises(ValueError):safe(self.root,'../credentials.json')


class ReviewServerTests(LibraryFixture):
    # Keep the HTTP tests separate from the model/registry tests.
    def test_http_review_requires_local_token_and_saved_notes(self):
        self.imported();server=build_server(self.root,audio_root=self.base/'missing-source-pool')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            response=requests.get(base+'/api/library',timeout=5)
            self.assertEqual(len(response.json()['assets']),1)
            payload={'id':self.record['id'],'status':'pass','notes':'Usable spare','listened':True}
            self.assertEqual(requests.post(base+'/api/review',json=payload,timeout=5).status_code,403)
            headers={'X-Review-Token':server.review_token,'Origin':base}
            self.assertEqual(requests.post(base+'/api/review',json=payload,headers=headers,timeout=5).status_code,200)
            self.assertEqual(len(pool(self.root,status='pass')),1)
            generation=requests.post(base+'/api/generate',json={'presets':['roof-light'],'seed':123,'duration':90},headers=headers,timeout=5)
            self.assertEqual(generation.status_code,200)
            self.assertEqual(generation.json()['results'][0]['status'],'needs_source')
            invalid=requests.post(base+'/api/generate',json={'presets':['roof-light'],'seed':'invalid'},headers=headers,timeout=5)
            self.assertEqual(invalid.status_code,400)
            self.assertEqual(requests.get(base+'/media/custom-audio%3Asample/listen.mp3',timeout=5).content,b'listening copy')
            headers['Origin']='https://untrusted.example'
            self.assertEqual(requests.post(base+'/api/review',json=payload,headers=headers,timeout=5).status_code,403)
            self.assertEqual(requests.get(base+'/media/../library.json',timeout=5).status_code,404)
            self.assertEqual(requests.get(base,headers={'Host':'other.example'},timeout=5).status_code,403)
        finally:
            server.shutdown();server.server_close();thread.join()

import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import media_local as media

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.studio = media.MediaStudio(self.tmp.name)
        out = io.BytesIO()
        Image.new('RGB', (2, 2), 'blue').save(out, 'PNG')
        self.png = out.getvalue()

    def profile(self, adapter='images', kind='image', **extra):
        return self.studio.save_profile(dict(name='Test', adapter=adapter, kind=kind,
            base_url='https://api.replicate.com/v1' if adapter == 'replicate' else 'http://127.0.0.1:8188',
            model='owner/model', workflow={'1': {'inputs': {'text': '__PROMPT__'}}}, **extra))

    def job(self, profile):
        with patch.object(media.threading.Thread, 'start'):
            return self.studio.create(dict(profile_id=profile['id'], prompt='A blue square', nonce='a-valid-request-12345'))

    def test_images_result_and_private_key(self):
        p = self.profile(key='unit-test-credential')
        self.assertNotIn('unit-test-credential', json.dumps(self.studio.catalog()))
        j = self.job(p)
        with patch.object(media, 'json_request', return_value={'data': [{'b64_json': base64.b64encode(self.png).decode()}]}) as call:
            self.studio.run(j, self.studio.profiles()[0])
        self.assertEqual(j['status'], 'done')
        with Image.open(self.studio.file(j['id'])) as image:
            self.assertEqual(image.size, (2, 2))
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.args[1]['prompt'], 'A blue square')
        self.assertEqual(self.studio.file(j['id']).stat().st_mode & 0o777, 0o600)

    def test_nonce_is_idempotent(self):
        p = self.profile()
        j = self.job(p)
        self.assertEqual(self.job(p)['id'], j['id'])
        with self.assertRaises(ValueError):
            self.studio.create(dict(profile_id=p['id'], prompt='different', nonce=j['nonce']))
        self.assertEqual(len(self.studio.jobs()), 1)

    def test_failure_does_not_retry_and_redacts_key(self):
        p = self.profile(key='unit-test-credential')
        j = self.job(p)
        with patch.object(media, 'json_request', side_effect=TimeoutError('unit-test-credential timeout')) as call:
            self.studio.run(j, self.studio.profiles()[0])
        self.assertEqual(call.call_count, 1)
        self.assertEqual(j['status'], 'uncertain')
        self.assertNotIn('unit-test-credential', j['error'])

    def test_restart_marks_unfinished_without_resubmission(self):
        j = self.job(self.profile())
        with patch.object(media, 'json_request') as call:
            other = media.MediaStudio(self.tmp.name)
        self.assertEqual(other.jobs()[0]['status'], 'uncertain')
        call.assert_not_called()

    def test_replicate_polls_only_get_after_creation(self):
        p = self.profile('replicate', 'video')
        j = self.job(p)
        with patch.object(media, 'json_request', side_effect=[{'id': 'abc', 'status': 'processing'}, {'id': 'abc', 'status': 'succeeded', 'output': 'https://example.com/video.mp4'}]) as call, patch.object(media.time, 'sleep'), patch.object(self.studio, 'download', return_value=b'\0\0\0\x18ftypisomtest'):
            self.studio.run(j, self.studio.profiles()[0])
        self.assertEqual(j['status'], 'done')
        self.assertEqual(len(call.call_args_list[0].args), 3)
        self.assertEqual(call.call_args_list[1].args, ('https://api.replicate.com/v1/predictions/abc',))
        self.assertEqual(j['file'], 'result.mp4')

    def test_comfy_replaces_prompt_and_fetches_result(self):
        p = self.profile('comfyui')
        j = self.job(p)
        with patch.object(media, 'json_request', side_effect=[{'prompt_id': 'abc'}, {'abc': {'outputs': {'9': {'images': [{'filename': 'image.png', 'type': 'output'}]}}}}]) as call, patch.object(media, 'request', return_value=(self.png, 'image/png')):
            self.studio.run(j, self.studio.profiles()[0])
        self.assertEqual(j['status'], 'done')
        self.assertEqual(call.call_args_list[0].args[1]['prompt']['1']['inputs']['text'], j['prompt'])

    def test_private_remote_and_cross_origin_outputs_rejected(self):
        for url in ['http://example.com/a', 'http://127.0.0.1/a', 'https://10.0.0.1/a', 'https://user:pass@example.com/a']:
            with self.subTest(url=url), self.assertRaises(ValueError): media.request(url)
        with self.assertRaises(ValueError): media.endpoint('https://example.com', local_only=True)
        with self.assertRaises(ValueError): self.studio.file('../../keys')

if __name__ == '__main__': unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from local_runtime import LocalRuntime


class LocalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'sever-ide/.local'
        self.data.mkdir(parents=True)
        self.config = self.root / 'local-assistant/model-9b.json'
        self.config.parent.mkdir()
        self.model = self.root / 'weights'
        self.model.mkdir()
        self.runtime = LocalRuntime(self.data, self.root / 'sever-ide/backend/worker.py')
        for target, value in [('platform.system', 'Darwin'), ('platform.machine', 'arm64'), ('importlib.util.find_spec', object())]:
            mocked = patch('local_runtime.' + target, return_value=value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def install(self):
        self.config.write_text(json.dumps({'path': str(self.model)}))
        (self.model / 'config.json').write_text('{}')
        (self.model / 'model.safetensors').touch()

    def test_missing_setup_is_not_reported_as_ready_to_load(self):
        self.assertEqual(self.runtime.state()['status'], 'unavailable')
        with patch('local_runtime.subprocess.Popen') as process:
            with self.assertRaisesRegex(ValueError, 'ещё не настроена'):
                self.runtime.submit({})
            process.assert_not_called()

    def test_missing_weights_and_dependencies_have_useful_errors(self):
        self.config.write_text(json.dumps({'path': str(self.model)}))
        self.assertIn('Файлы Qwen не найдены', self.runtime.installation_error())
        self.install()
        with patch('local_runtime.importlib.util.find_spec', return_value=None):
            self.assertIn('установить mlx-lm', self.runtime.state()['reason'])

    def test_invalid_config_does_not_crash_state(self):
        for value in ['[]', '{', '{"path":42}', '{"path":""}', '{"path":"relative"}']:
            with self.subTest(config=value):
                self.config.write_text(value)
                self.assertEqual(self.runtime.state()['status'], 'unavailable')

    def test_failed_resident_load_is_an_error_instead_of_infinite_loading(self):
        self.install()
        self.runtime.process = Mock()
        self.runtime.process.poll.return_value = None
        self.runtime.run = self.data / 'run'
        self.runtime.run.mkdir()
        self.assertEqual(self.runtime.state()['status'], 'loading')
        (self.runtime.run / 'report.json').write_text(json.dumps({'status': 'error', 'final': 'Model could not load'}))
        (self.runtime.run / 'resident.done').touch()
        state = self.runtime.state()
        self.assertEqual(state['status'], 'error')
        self.assertEqual(state['reason'], 'Model could not load')

    def test_loaded_model_stays_ready_after_generation_error(self):
        self.install()
        self.assertEqual(self.runtime.state()['status'], 'cold')
        self.runtime.process = Mock()
        self.runtime.process.poll.return_value = None
        self.runtime.run = self.data / 'run'
        self.runtime.run.mkdir()
        (self.runtime.run / 'report.json').write_text('{"status":"error"}')
        (self.data / 'model-ready.json').write_text('{}')
        self.assertEqual(self.runtime.state()['status'], 'ready')

    def test_crashed_worker_is_reported_as_error(self):
        self.install()
        self.runtime.process = Mock()
        self.runtime.process.poll.return_value = -9
        self.runtime.run = self.data / 'run'
        self.runtime.run.mkdir()
        self.assertEqual(self.runtime.state()['status'], 'error')


if __name__ == '__main__':
    unittest.main()

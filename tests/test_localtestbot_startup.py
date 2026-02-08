import unittest
from unittest import mock

from sgbridgebot import localtestbot


class LocalTestBotStartupValidationTests(unittest.TestCase):
    def test_main_exits_cleanly_when_token_missing(self):
        with mock.patch.dict(localtestbot.os.environ, {}, clear=True):
            with mock.patch.object(localtestbot, 'ChatBot') as chat_bot_mock:
                with self.assertRaises(SystemExit) as exc:
                    localtestbot.main()

        self.assertEqual(exc.exception.code, 1)
        chat_bot_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()

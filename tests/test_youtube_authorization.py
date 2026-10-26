import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response
from upload_youtube import verify_target_channel
import get_youtube_refresh_token as helper


class AuthorizationTests(unittest.TestCase):
    def test_missing_channel_fails_before_network(self):
        youtube = Mock()
        with patch.dict(os.environ, {"EXPECTED_YOUTUBE_CHANNEL_ID": ""}):
            with self.assertRaisesRegex(RuntimeError, "repository variable"):
                verify_target_channel(youtube)
        youtube.channels.assert_not_called()

    def test_wrong_channel_is_rejected(self):
        youtube = Mock()
        youtube.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "UCwrong", "snippet": {"title": "Wrong channel"}}]
        }
        with patch.dict(os.environ, {"EXPECTED_YOUTUBE_CHANNEL_ID": "UCexpected"}):
            with self.assertRaisesRegex(RuntimeError, "Refusing to upload"):
                verify_target_channel(youtube)

    def test_old_scope_error_explains_reauthorization(self):
        youtube = Mock()
        youtube.channels.return_value.list.return_value.execute.side_effect = RefreshError("invalid_scope")
        with patch.dict(os.environ, {"EXPECTED_YOUTUBE_CHANNEL_ID": "UCexpected"}):
            with self.assertRaisesRegex(RuntimeError, "replace the three YT_"):
                verify_target_channel(youtube)

    def test_signup_required_is_retried_once_then_explained(self):
        signup = HttpError(Response({"status": 401, "content-type": "application/json"}),
                           b'{"error": {"code": 401, "message": "Unauthorized", "errors": '
                           b'[{"domain": "youtube.header", "reason": "youtubeSignupRequired"}]}}')
        ok = {"items": [{"id": "UCexpected", "snippet": {"title": "Rain"}}]}
        youtube = Mock()
        execute = youtube.channels.return_value.list.return_value.execute
        with patch.dict(os.environ, {"EXPECTED_YOUTUBE_CHANNEL_ID": "UCexpected"}), \
                patch("upload_youtube.time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            execute.side_effect = [signup, ok]
            verify_target_channel(youtube)
            execute.side_effect = [signup, signup]
            with self.assertRaisesRegex(RuntimeError, "youtubeSignupRequired twice"):
                verify_target_channel(youtube)
        self.assertEqual(sleep.call_count, 2)

    def test_missing_refresh_token_never_prints_secrets(self):
        flow = Mock()
        flow.run_local_server.return_value.refresh_token = None
        output = io.StringIO()
        with patch.object(sys, "argv", ["helper", "--expected-channel-id", "UCexpected"]), \
                patch.object(helper.InstalledAppFlow, "from_client_secrets_file", return_value=flow), \
                contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, "did not return a refresh token"):
                helper.main()
        self.assertNotIn("YT_REFRESH_TOKEN=", output.getvalue())
        flow.run_local_server.assert_called_once_with(
            port=0, access_type="offline", prompt="consent select_account"
        )


if __name__ == "__main__":
    unittest.main()

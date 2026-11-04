"""Offline importer tests: no AI, real cookies, or external network."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

MODULE_ROOT = Path(__file__).resolve().parent
if not (MODULE_ROOT/'youtube_support.py').is_file(): MODULE_ROOT = MODULE_ROOT.parent
sys.path.insert(0,str(MODULE_ROOT))
import youtube_support as youtube
import claude_real_video.core as core

URL='https://www.youtube.com/watch?v=Q2w4-mluYo0'


class YouTubeImportTests(unittest.TestCase):
    def test_policy_enables_javascript_without_cookie_or_proxy(self):
        with patch.object(youtube.shutil,'which',return_value='/usr/local/bin/node'):
            args=youtube.youtube_args('android_vr')
        for required in ('--ignore-config','--no-plugin-dirs','--no-playlist','--js-runtimes','node:/usr/local/bin/node','^youtube$'):
            self.assertIn(required,args)
        self.assertFalse(any('cookies' in v or 'proxy' in v for v in args))
        self.assertIn('youtube:player_client=android_vr',args)

    def test_only_validated_youtube_urls_receive_new_policy(self):
        self.assertTrue(youtube.is_youtube(URL))
        self.assertTrue(youtube.is_youtube('https://youtu.be/Q2w4-mluYo0'))
        for value in ('https://youtube.com.evil.invalid/watch?v=Q2w4-mluYo0','file:///etc/passwd','https://127.0.0.1',None):
            self.assertFalse(youtube.is_youtube(value))

    def test_success_does_not_retry_and_keeps_caption_and_quality_options(self):
        with patch.object(core,'fetch_video',return_value='source.mp4') as original:
            with youtube.youtube_context():
                result=core.fetch_video(URL,'folder',ytdlp_args=['-S','res:1080'],sub_lang='ja')
            self.assertEqual(original.call_count,1)
            self.assertEqual(result,'source.mp4')
            self.assertEqual(original.call_args.args[-1],'ja')
            self.assertEqual(original.call_args.args[-2][:2],['-S','res:1080'])

    def test_client_fallback_is_bounded_and_only_after_transport_errors(self):
        with patch.object(core,'fetch_video',side_effect=[RuntimeError("Sign in to confirm you’re not a bot"),RuntimeError('HTTP 403'),'source.mp4']) as original:
            with youtube.youtube_context(): self.assertEqual(core.fetch_video(URL,'folder'),'source.mp4')
            self.assertEqual(original.call_count,3)
            self.assertIn('youtube:player_client=android_vr',original.call_args_list[1].args[-2])
            self.assertIn('youtube:player_client=web_embedded',original.call_args_list[2].args[-2])

    def test_private_video_is_not_retried(self):
        with patch.object(core,'fetch_video',side_effect=RuntimeError('Private video')) as original:
            with youtube.youtube_context(),self.assertRaises(RuntimeError):core.fetch_video(URL,'folder')
            self.assertEqual(original.call_count,1)

    def test_no_personal_cookies_are_sent(self):
        with patch.object(core,'fetch_video') as original:
            with youtube.youtube_context(),self.assertRaises(ValueError):core.fetch_video(URL,'folder',cookies='personal.txt')
            original.assert_not_called()

    def test_non_youtube_behavior_is_unchanged(self):
        with patch.object(core,'fetch_video',return_value='source.mp4') as original:
            with youtube.youtube_context():core.fetch_video('local.mp4','folder',ytdlp_args=['-S','res:1080'],sub_lang='ja')
            self.assertEqual(original.call_args.args,('local.mp4','folder',None,None,['-S','res:1080'],'ja'))

    def test_bot_failure_is_not_claimed_as_success_or_retried_forever(self):
        with patch.object(core,'fetch_video',side_effect=RuntimeError("Sign in to confirm you’re not a bot")) as original:
            with youtube.youtube_context(),self.assertRaises(RuntimeError) as caught:core.fetch_video(URL,'folder')
            self.assertEqual(original.call_count,3)
            self.assertEqual(youtube.error_code(caught.exception),'youtube_verification')


if __name__=='__main__':unittest.main()

from pathlib import Path
import sys,json,unittest,subprocess
from types import SimpleNamespace
from unittest.mock import patch,Mock,MagicMock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import youtube_browser as browser

URL='https://www.youtube.com/watch?v=Q2w4-mluYo0'

class BrowserImportTests(unittest.TestCase):
    def test_only_validated_youtube_sources_are_accepted(self):
        for source in ('http://127.0.0.1/','https://youtube.com.evil.invalid/watch?v=Q2w4-mluYo0','file:///etc/passwd','https://x.com/i/web/status/1'):
            with self.assertRaises(ValueError):browser.browser_args(source,ROOT)
        self.assertEqual(browser.browser_args('https://youtu.be/Q2w4-mluYo0',ROOT)[-1],URL)

    def test_browser_keeps_quality_and_uses_only_pinned_provider(self):
        args=browser.browser_args(URL,ROOT,'ja')
        for v in ('--ignore-config','--no-plugin-dirs',str(browser.PLUGINS),'res:1080','--no-playlist','youtubepot-wpc:browser_path='+str(browser.CHROME)):
            self.assertIn(v,args)
        self.assertIn('youtube:player_client=mweb;fetch_pot=always;pot_trace=true',args)
        self.assertFalse(any('cookies' in v or 'proxy' in v or 'no-sandbox' in v for v in args))
        self.assertEqual(args[-3:],['--write-auto-subs','--sub-langs','ja'])

    def test_python_api_explicitly_loads_only_selected_plugin_directory(self):
        from yt_dlp.globals import plugin_dirs
        original=plugin_dirs.value
        try:
            with patch.object(browser,'PLUGINS',ROOT), patch('yt_dlp.plugins.load_all_plugins') as load:
                opts=browser.ydl_options(URL,ROOT,Mock())
            load.assert_called_once()
            self.assertEqual(plugin_dirs.value,[str(ROOT)])
            self.assertIsNone(opts.get('cookiefile'))
            self.assertIsNone(opts.get('cookiesfrombrowser'))
        finally:
            plugin_dirs.value=original

    def test_browser_diagnostic_preserves_sandbox_and_redacts_stderr(self):
        with patch.object(browser.subprocess,'run',return_value=Mock(returncode=1,stderr='No usable sandbox! secret-do-not-log',stdout='')) as run:
            result=browser.browser_start_diagnostic(ROOT)
        self.assertEqual(result,'sandbox_unavailable')
        self.assertNotIn('--no-sandbox',run.call_args.args[0])
        self.assertNotIn('secret-do-not-log',result)

    def test_only_temporary_xvfb_display_survives_environment_filter(self):
        env=browser.worker_environment(ROOT,{'DISPLAY':':123','XAUTHORITY':str(ROOT/'xvfb/Xauthority'),'OPENROUTER_API_KEY':'secret'})
        self.assertEqual(env['DISPLAY'],':123')
        self.assertNotIn('OPENROUTER_API_KEY',env)
        for display,authority in [('remote-host:0',str(ROOT/'Xauthority')),(':123',str(ROOT.parent/'personal-Xauthority'))]:
            env=browser.worker_environment(ROOT,{'DISPLAY':display,'XAUTHORITY':authority})
            self.assertNotIn('DISPLAY',env)
            self.assertNotIn('XAUTHORITY',env)

    def test_chromium_command_restores_security_and_private_profile(self):
        config=Mock(return_value=['--disable-features=IsolateOrigins,site-per-process','--no-sandbox','--ignore-certificate-errors','--user-data-dir=temporary','--remote-debugging-port=123'])
        command=browser.chromium_command(config,ROOT)
        self.assertTrue(config.sandbox)
        self.assertEqual(config.user_data_dir,str(ROOT/'anonymous-chrome-profile'))
        self.assertFalse(any('no-sandbox' in x or 'disable-features' in x or 'ignore-certificate-errors' in x for x in command))
        self.assertIn('--remote-debugging-address=127.0.0.1',command)

    def test_probe_isolated_profile_sanitized_env_and_safe_logs(self):
        folder=MagicMock();folder.__enter__.return_value='/fresh-ephemeral-profile'
        proc=Mock(returncode=1);proc.communicate.return_value=(json.dumps({'success':False,'provider_loaded':True,'error_code':'youtube_verification','cookie':'secret-must-not-appear'}),'private details')
        with patch.object(browser.tempfile,'TemporaryDirectory',return_value=folder), patch.object(browser.subprocess,'Popen',return_value=proc) as spawn, patch.dict(browser.os.environ,{'OPENROUTER_API_KEY':'secret-must-not-appear','VIDEO_PDF_ACCESS_PASSWORD':'secret-must-not-appear'}), patch('builtins.print') as output:
            report=browser.browser_probe(URL,ROOT)
        env=spawn.call_args.kwargs['env']
        self.assertEqual(env['HOME'],'/fresh-ephemeral-profile')
        self.assertEqual(env['XDG_CONFIG_HOME'],env['HOME'])
        self.assertNotIn('OPENROUTER_API_KEY',env)
        self.assertNotIn('VIDEO_PDF_ACCESS_PASSWORD',env)
        self.assertNotIn('secret-must-not-appear',str(output.call_args_list))
        self.assertFalse(report['success']);self.assertEqual(report['ai_calls'],0)
        self.assertNotIn('cookie',report)
        proc.communicate.assert_called_once_with(timeout=240)
        folder.__exit__.assert_called_once()

    def test_timeout_kills_download_and_browser_process_group(self):
        folder=MagicMock();folder.__enter__.return_value='/fresh-ephemeral-profile'
        proc=Mock(pid=777,returncode=-9);proc.communicate.side_effect=[subprocess.TimeoutExpired('test',240),('','')]
        with patch.object(browser.tempfile,'TemporaryDirectory',return_value=folder), patch.object(browser.subprocess,'Popen',return_value=proc), patch.object(browser,'os',SimpleNamespace(name='posix',killpg=Mock())) as fake_os, patch.object(browser.signal,'SIGKILL',9,create=True), patch('builtins.print'):
            report=browser.browser_probe(URL,ROOT)
        self.assertFalse(report['success']);self.assertEqual(report['error_code'],'timeout')
        fake_os.killpg.assert_called_once_with(777,9)
        folder.__exit__.assert_called_once()

if __name__=='__main__':unittest.main()

"""Deployment pieces: installer, operator CLI wrapper, backups, status, and
graceful shutdown. Runs the real shell scripts against temporary prefixes."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DEPLOY = HERE / "deploy"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)


class TestOperatorWrapper(unittest.TestCase):
    def test_env_file_is_parsed_literally_never_executed(self):
        with tempfile.TemporaryDirectory() as root:
            r = Path(root)
            (r / "etc/tradebot").mkdir(parents=True)
            (r / "var/lib/tradebot").mkdir(parents=True)
            venv_bin = r / "opt/tradebot/venv/bin"
            venv_bin.mkdir(parents=True)
            # Fake interpreter: prints what the bot would see.
            (venv_bin / "python").write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                printf 'SECRET=[%s]\\nARGS=[%s]\\nMODE=[%s]\\nCWD=[%s]\\nARGV=[%s]\\n' \\
                    "$KITE_API_SECRET" "$TRADEBOT_ARGS" "$TRADEBOT_MODE" "$PWD" "$*"
            """))
            (venv_bin / "python").chmod(0o755)
            (r / "etc/tradebot/env").write_text(
                "# comment\n\n"
                f"KITE_API_SECRET=ab$HOME`touch {root}/pwned`$(id)x\n"
                'TRADEBOT_ARGS="--feed kite --faults reject=0.1"\n'
                "TRADEBOT_MODE='paper'\n"
                "not a valid line\n")
            out = run([str(DEPLOY / "tradebot.sh"), "status", "-c", "x.json"],
                      env={**os.environ, "TRADEBOT_INSTALL_ROOT": root})
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn(f"SECRET=[ab$HOME`touch {root}/pwned`$(id)x]", out.stdout)
            self.assertIn("ARGS=[--feed kite --faults reject=0.1]", out.stdout)
            self.assertIn("MODE=[paper]", out.stdout)
            self.assertIn(f"CWD=[{r / 'var/lib/tradebot'}]", out.stdout)
            self.assertIn("ARGV=[-m tradebot status -c x.json]", out.stdout)
            self.assertFalse((r / "pwned").exists(), "env file content was executed")


class TestBackup(unittest.TestCase):
    def test_backup_excludes_token_and_prunes_old(self):
        with tempfile.TemporaryDirectory() as d:
            state, out = Path(d) / "state", Path(d) / "bk"
            (state / "state/swing").mkdir(parents=True)
            (state / "state/swing/bot_state.json").write_text("{}")
            (state / "state/kite_token.json").write_text('{"access_token": "secret"}')
            (state / "state/swing/bot_state.tmp").write_text("partial")
            out.mkdir()
            old = out / "tradebot-state-20200101T000000Z.tar.gz"
            old.write_text("x")
            os.utime(old, (time.time() - 40 * 86400,) * 2)
            res = run([str(DEPLOY / "backup.sh"), str(state), str(out), "30"])
            self.assertEqual(res.returncode, 0, res.stderr)
            archives = sorted(out.glob("tradebot-state-*.tar.gz"))
            self.assertEqual(len(archives), 1)              # old one pruned
            names = run(["tar", "tzf", str(archives[0])]).stdout
            self.assertIn("bot_state.json", names)
            self.assertNotIn("kite_token", names)
            self.assertNotIn(".tmp", names)


class TestInstaller(unittest.TestCase):
    def test_install_then_upgrade_preserves_operator_files(self):
        with tempfile.TemporaryDirectory() as root:
            env = {**os.environ, "TRADEBOT_INSTALL_ROOT": root, "TRADEBOT_SKIP_PIP": "1"}
            first = run([str(DEPLOY / "install.sh")], env=env)
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            r = Path(root)
            for p in ("opt/tradebot/app/tradebot/live.py", "opt/tradebot/venv/bin/python",
                      "etc/tradebot/swing.json", "etc/tradebot/env", "usr/local/bin/tradebot",
                      "etc/systemd/system/tradebot@.service", "etc/systemd/system/tradebot-backup.timer",
                      "opt/tradebot/app/deploy/backup.sh"):
                self.assertTrue((r / p).exists(), p)
            self.assertEqual((r / "etc/tradebot/env").stat().st_mode & 0o777, 0o640)
            self.assertEqual((r / "var/lib/tradebot").stat().st_mode & 0o777, 0o700)
            self.assertFalse(list(r.glob("opt/tradebot/app/**/__pycache__")))
            cfg = r / "etc/tradebot/swing.json"
            cfg.write_text(cfg.read_text().replace('"initial_capital": 500000', '"initial_capital": 123456'))
            (r / "etc/tradebot/env").write_text("KITE_API_KEY=mine\n")
            second = run([str(DEPLOY / "install.sh")], env=env)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("123456", cfg.read_text())                    # operator edits kept
            self.assertEqual((r / "etc/tradebot/env").read_text(), "KITE_API_KEY=mine\n")
            self.assertTrue((r / "opt/tradebot/app.old").is_dir())       # previous code kept for rollback

    def test_installed_configs_are_valid_for_paper_and_live(self):
        sys.path.insert(0, str(HERE))
        from tradebot.config import Config
        for f in (HERE / "config").glob("*.json"):
            c = Config.load(f)
            self.assertTrue(c.sectors, f"{f.name} has no sectors map; paper/live would refuse it")


class TestStatusAndShutdown(unittest.TestCase):
    def test_status_and_sigterm_finishes_cycle_and_saves(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cfg = {"mode": "swing", "strategy": "donchian", "symbols": ["A"], "interval": "day",
                   "state_file": str(d / "state/bot_state.json"), "kill_switch_file": str(d / "STOP"),
                   "sectors": {"A": "x"}, "risk": {"min_avg_turnover": 0, "min_price": 0}}
            (d / "c.json").write_text(json.dumps(cfg))
            # A child process running the real engine loop against a fake feed.
            script = textwrap.dedent(f"""
                import sys, pandas as pd
                sys.path.insert(0, {str(HERE)!r})
                from tradebot.config import Config
                from tradebot.broker import PaperBroker
                from tradebot.live import LiveEngine
                from tradebot.strategies import make_strategy
                from tests.test_tradebot import FakeFeed, bars
                cfg = Config.load({str(d / 'c.json')!r})
                df = bars([(100, 101, 99, 100, 1e6)] * 5, freq="B")
                eng = LiveEngine(cfg, make_strategy("donchian"), PaperBroker(FakeFeed(df), 0.0),
                                 now=lambda: df.index[2] + pd.Timedelta(hours=10))
                print("ready", flush=True)
                eng.run(poll_seconds=60)
            """)
            p = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
            self.assertEqual(p.stdout.readline().strip(), "ready")
            time.sleep(1.5)                             # let it finish a cycle and start sleeping
            p.send_signal(signal.SIGTERM)
            _, err = p.communicate(timeout=20)
            self.assertEqual(p.returncode, 0, err)        # clean exit -> systemd won't restart it
            self.assertIn("stop requested", err)
            self.assertTrue((d / "state/bot_state.json").exists())
            st = run([sys.executable, "-m", "tradebot", "status", "-c", str(d / "c.json")],
                     cwd=str(HERE))
            self.assertEqual(st.returncode, 0, st.stderr)
            self.assertIn("swing/donchian", st.stdout)
            self.assertIn("halts: none", st.stdout)
            self.assertIn("positions (0)", st.stdout)


if __name__ == "__main__":
    unittest.main()

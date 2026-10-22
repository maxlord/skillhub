"""security-lint tests: a safe skill is ok, each kind of leak or dangerous operation is blocked.

Run: `python3 -m pytest tools/` or `python3 -m unittest discover -s tools/tests`.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import security_lint as sl  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "security"
HOSTS = FIX.parent / "spec" / "catalog" / "public-hosts.yaml"
PUB = sl.load_public_hosts(HOSTS)


def rules(text: str) -> set[str]:
    return {f.rule for f in sl.scan_text(text, "x.md", PUB)}


class SecurityLintTest(unittest.TestCase):
    # --- whole skills ----------------------------------------------------------------

    def test_good_skill_ok(self):
        v = sl.scan_unit(FIX / "good" / "safe-skill", PUB)
        self.assertEqual("ok", v.flag, [str(f) for f in v.findings])

    def test_bad_skill_blocked_with_reasons(self):
        v = sl.scan_unit(FIX / "bad" / "leaky-skill", PUB)
        self.assertEqual("blocked", v.flag)
        self.assertTrue({"internal-ip", "ssh-nonstandard-port", "curl-token-literal",
                         "danger-compose-up-without-pinned-image"} <= set(v.reasons), v.reasons)

    def test_cli_writes_security_json_and_masks(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        out = tmp / "dist" / "security.json"
        rc = sl.main(["--hosts", str(HOSTS), "--out", str(out), str(FIX / "good"), str(FIX / "bad")])
        self.assertEqual(1, rc)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual("ok", data["safe-skill"]["flag"])
        self.assertEqual("blocked", data["leaky-skill"]["flag"])
        dumped = out.read_text(encoding="utf-8")
        self.assertNotIn("203.0.113.17", dumped)
        self.assertNotIn("2299", dumped)
        self.assertNotIn("0123456789abcdef0123456789abcdef01234567", dumped)

    def test_single_file_unit(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        f = tmp / "draft.md"
        f.write_text("Runner 198.51.100.4\n", encoding="utf-8")
        v = sl.lint([f], HOSTS)[0]
        self.assertEqual(("draft", "blocked"), (v.skill, v.flag))

    # --- secrets --------------------------------------------------------------------------

    def test_private_key(self):
        self.assertIn("secret-private-key", rules("-----BEGIN OPENSSH PRIVATE KEY-----"))

    def test_sk_key(self):
        self.assertIn("secret-anthropic-openai-key", rules("key sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA"))

    def test_github_token(self):
        self.assertIn("secret-github-token", rules("ghp_" + "a" * 36))

    def test_telegram_token(self):
        self.assertIn("secret-telegram-bot-token", rules("BOT=123456789:" + "A" * 35))

    def test_token_assignment(self):
        self.assertIn("secret-assignment", rules("token=abcdef123456"))
        self.assertIn("secret-assignment", rules('password: "hunter2hunter2"'))

    def test_assignment_with_variable_is_ok(self):
        self.assertEqual(set(), rules('token=$GITEA_TOKEN'))
        self.assertEqual(set(), rules("password: <from $SECRETS_DIR/x>"))
        self.assertEqual(set(), rules("passwords are kept by the owner, the token is in $SECRETS_DIR/git-token"))

    def test_dotsecrets_content(self):
        self.assertIn("secret-dotsecrets-content", rules(".secrets/test-pair.txt: user42 / pass42"))

    def test_ask_for_token(self):
        self.assertIn("ask-for-token", rules("Paste here your token and run"))
        self.assertIn("ask-for-token", rules("Please paste your API key below"))

    # --- curl/wget ---------------------------------------------------------------------------

    def test_curl_header_literal(self):
        self.assertIn("curl-token-literal", rules('curl -H "Authorization: Bearer abcdef123456" https://git.example.org'))

    def test_curl_bearer_variable_ok(self):
        for value in ("Bearer $TOKEN", "Bearer ${TOKEN}", "Bearer $GITEA_TOKEN", 'token $(cat "$TOKEN_FILE")',
                      "Bearer <token>", "$GITEA_TOKEN"):
            with self.subTest(value=value):
                self.assertEqual(set(), rules(f'curl -sf -H "Authorization: {value}" https://git.example.org/api'))

    def test_curl_bearer_literal(self):
        self.assertIn("curl-token-literal", rules('curl -H "Authorization: Bearer abcdef123456" https://x.example.com'))
        self.assertIn("curl-token-literal", rules("curl -H 'PRIVATE-TOKEN: abcdef123456' https://x.example.com"))

    def test_auth_header_literal_outside_curl(self):
        self.assertIn("auth-header-literal", rules("Authorization: Bearer abcdef123456"))
        self.assertIn("auth-header-literal", rules('headers = {"Authorization": "token abcdef123456"}'.replace('": "', ': ')))
        self.assertEqual(set(), rules("Authorization: Bearer $TOKEN"))
        self.assertEqual(set(), rules("Authorization: Bearer <token>"))

    def test_curl_url_token(self):
        self.assertIn("curl-token-literal", rules("curl https://git.example.org/api/v1/user?token=abcdef123456"))

    def test_curl_user_password(self):
        self.assertIn("curl-token-literal", rules("curl -u deploy:s3cretpass https://git.example.org"))

    def test_wget_password(self):
        self.assertIn("curl-token-literal", rules("wget --password=s3cretpass https://git.example.org/x"))

    def test_curl_with_env_ok(self):
        self.assertEqual(set(), rules('curl -H "Authorization: token $GITEA_TOKEN" https://git.example.org/api'))
        self.assertEqual(set(), rules("curl -sfn https://git.example.org/api/v1/user"))

    # --- internal addresses -------------------------------------------------------------------------

    def test_ip(self):
        self.assertIn("internal-ip", rules("prod is 192.0.2.10"))
        self.assertIn("internal-ip", rules("http://198.51.100.7:8080/metrics"))

    def test_loopback_and_versions_ok(self):
        self.assertEqual(set(), rules("listens on 127.0.0.1 and 0.0.0.0; version v0.17.0, 1.2.3"))

    def test_ssh_port(self):
        self.assertIn("ssh-nonstandard-port", rules('ssh -p 12366 "$HOST"'))
        self.assertIn("ssh-nonstandard-port", rules("Port 2299"))

    def test_ssh_tunnel(self):
        self.assertIn("ssh-tunnel", rules('ssh -N -R 1234:localhost:1234 "$MAC"'))

    def test_ssh_account_and_alias(self):
        self.assertIn("ssh-account", rules("ssh root@runner-box uptime"))
        self.assertNotIn("ssh-account", rules("ssh dev@127.0.0.1 uptime"))
        self.assertIn("ssh-host-alias", rules("ssh runner-box2 docker ps"))

    def test_internal_host(self):
        self.assertIn("internal-host", rules("cache at https://gradle-cache.corp-internal.lan/"))
        self.assertIn("internal-host", rules("server mybox.internal"))

    def test_public_hosts_ok(self):
        self.assertEqual(set(), rules("https://git.example.org/example-org and https://code.claude.com/docs"))
        self.assertEqual(set(), rules("files SKILL.md, plan.md, new-skill.sh, config.toml, hooks.json"))

    def test_shell_default_url(self):
        self.assertEqual(set(), rules("GIT_URL=${GIT_URL:-https://git.example.org}"))
        self.assertIn("internal-host", rules("CACHE=${CACHE:-https://gradle-cache.corp-internal.lan}"))

    # --- dangerous operations ---------------------------------------------------------------------------

    def test_rm_rf_without_stop(self):
        self.assertIn("danger-rm-rf", rules("Clean up:\n\nrm -rf /opt/ci/cache\n"))

    def test_rm_rf_with_stop(self):
        self.assertEqual(set(), rules("Human stop: confirm first.\nrm -rf /opt/ci/cache\n"))

    def test_rm_rf_allow_comment(self):
        self.assertEqual(set(), rules('rm -rf "$tmp"  # security-lint: allow danger-rm-rf - own tmp'))

    def test_push_force(self):
        self.assertIn("danger-push-force", rules("git push --force origin dev"))
        self.assertIn("danger-push-force", rules("git push -f origin dev"))

    def test_image_prune_all(self):
        self.assertIn("danger-image-prune-all", rules("docker image prune -af"))
        self.assertEqual(set(), rules("docker image prune -f"))

    def test_compose_up(self):
        self.assertIn("danger-compose-up-without-pinned-image", rules("docker compose up -d api"))
        self.assertEqual(set(), rules("APP_IMAGE=$IMG docker compose up -d api"))
        self.assertEqual(set(), rules("export APP_IMAGE=$IMG\ndocker compose up -d api"))
        self.assertEqual(set(), rules("docker compose up -d --no-build api"))
        self.assertIn("danger-compose-up-without-pinned-image", rules("docker compose -f prod.yml up -d"))
        self.assertEqual(set(), rules("name: prod-compose-up-needs-pinned-image"))

    # --- masking -------------------------------------------------------------------------------

    def test_mask_line(self):
        masked = sl.mask_line("ssh -p 2299 ops@192.0.2.10")
        self.assertNotIn("2299", masked)
        self.assertNotIn("192.0.2.10", masked)
        self.assertNotIn("ops@", masked)


if __name__ == "__main__":
    unittest.main()

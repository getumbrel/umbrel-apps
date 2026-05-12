from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "mastodon"


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_mastodon_manifest_declares_umbrel_app_metadata():
    manifest = read_yaml(APP / "umbrel-app.yml")

    assert manifest["id"] == "mastodon"
    assert manifest["category"] == "social"
    assert manifest["name"] == "Mastodon"
    assert manifest["port"] == 8388
    assert manifest["repo"] == "https://github.com/mastodon/mastodon"
    assert manifest["gallery"] == []
    assert manifest["releaseNotes"] == ""


def test_mastodon_icon_does_not_pre_round_corners():
    icon = (APP / "icon.svg").read_text(encoding="utf-8")

    assert "rx=" not in icon


def test_mastodon_port_is_not_used_by_an_existing_app():
    mastodon_port = read_yaml(APP / "umbrel-app.yml")["port"]
    existing_ports = {
        read_yaml(path).get("port")
        for path in ROOT.glob("*/umbrel-app.yml")
        if path.parent.name != "mastodon"
    }

    assert mastodon_port not in existing_ports


def test_mastodon_compose_uses_pinned_images_and_required_services():
    compose = read_yaml(APP / "docker-compose.yml")
    services = compose["services"]

    assert services["app_proxy"]["environment"]["APP_HOST"] == "mastodon_proxy_1"
    assert services["app_proxy"]["environment"]["APP_PORT"] == 80

    for service_name in ["proxy", "web", "streaming", "sidekiq", "db", "redis"]:
        image = services[service_name]["image"]
        assert "@sha256:" in image, f"{service_name} image must be digest-pinned"

    assert services["web"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert services["web"]["depends_on"]["redis"]["condition"] == "service_healthy"
    assert "mastodon-streaming" in services["streaming"]["image"]
    assert services["sidekiq"]["command"] == ["bundle", "exec", "sidekiq"]
    assert services["streaming"]["command"] == ["node", "./streaming"]


def test_mastodon_proxy_routes_web_and_streaming_api():
    proxy_config = (APP / "nginx.conf").read_text(encoding="utf-8")

    assert "proxy_pass http://web:3000;" in proxy_config
    assert "location /api/v1/streaming" in proxy_config
    assert "proxy_pass http://streaming:4000;" in proxy_config
    assert "proxy_set_header Upgrade $http_upgrade;" in proxy_config
    assert proxy_config.count("proxy_set_header Host $host;") == 2


def test_mastodon_http_initializer_is_mounted_for_rails_services():
    compose = read_yaml(APP / "docker-compose.yml")
    services = compose["services"]
    initializer_mount = (
        "${APP_DATA_DIR}/force-http.rb:"
        "/opt/mastodon/config/initializers/99_umbrel_force_http.rb:ro"
    )
    initializer = (APP / "force-http.rb").read_text(encoding="utf-8")

    for service_name in ["web", "sidekiq", "migrate"]:
        assert initializer_mount in services[service_name]["volumes"]

    assert "config.force_ssl = false" in initializer
    assert "ws://#{config.x.web_domain}" in initializer


def test_mastodon_compose_persists_data_and_uses_generated_env_file():
    compose = read_yaml(APP / "docker-compose.yml")
    services = compose["services"]

    assert "${APP_DATA_DIR}/data/system:/mastodon/public/system" in services["web"]["volumes"]
    assert "${APP_DATA_DIR}/data/db:/var/lib/postgresql/data" in services["db"]["volumes"]
    assert "${APP_DATA_DIR}/data/redis:/data" in services["redis"]["volumes"]

    for service_name in ["web", "streaming", "sidekiq"]:
        assert services[service_name]["env_file"] == ["${APP_DATA_DIR}/mastodon.env"]


def test_mastodon_pre_start_generates_required_secrets():
    hook = (APP / "hooks" / "pre-start").read_text(encoding="utf-8")

    for key in [
        "SECRET_KEY_BASE",
        "OTP_SECRET",
        "VAPID_PRIVATE_KEY",
        "VAPID_PUBLIC_KEY",
        "LOCAL_DOMAIN",
        "WEB_DOMAIN",
    ]:
        assert key in hook

    assert "DB_HOST=db" in hook
    assert "REDIS_HOST=redis" in hook
    assert "LOCAL_HTTPS=false" in hook
    assert "force-http.rb" in hook
    assert "chown -R 1000:1000" in hook
    assert "172.16.0.0/12" in hook


def test_mastodon_pre_start_is_safe_when_template_files_are_already_in_app_data(tmp_path):
    app_data = tmp_path / "mastodon"
    shutil.copytree(APP, app_data)

    (app_data / "mastodon.env").write_text(
        "\n".join(
            [
                "SECRET_KEY_BASE=existing-secret-key-base",
                "OTP_SECRET=existing-otp-secret",
                "VAPID_PRIVATE_KEY=existing-vapid-private-key",
                "VAPID_PUBLIC_KEY=existing-vapid-public-key",
                "ACTIVE_RECORD_ENCRYPTION_DETERMINISTIC_KEY=existing-deterministic-key",
                "ACTIVE_RECORD_ENCRYPTION_KEY_DERIVATION_SALT=existing-key-derivation-salt",
                "ACTIVE_RECORD_ENCRYPTION_PRIMARY_KEY=existing-primary-key",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        ["bash", str(app_data / "hooks" / "pre-start")],
        check=True,
        env={
            "APP_DATA_DIR": str(app_data),
            "DEVICE_DOMAIN_NAME": "umbrel-dev.local",
            "APP_HIDDEN_SERVICE": "not-enabled.onion",
        },
    )

    env_file = (app_data / "mastodon.env").read_text(encoding="utf-8")
    assert "LOCAL_DOMAIN=umbrel-dev.local" in env_file
    assert "WEB_DOMAIN=umbrel-dev.local:8388" in env_file

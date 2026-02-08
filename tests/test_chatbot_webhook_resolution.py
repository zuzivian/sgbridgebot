import os
from unittest import mock

import pytest

from sgbridgebot import main
from sgbridgebot.ChatBot import _resolve_webhook_base_url, _resolve_webhook_listen_port


def test_resolve_webhook_base_url_from_env(monkeypatch):
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com/")
    monkeypatch.delenv("KOYEB_PUBLIC_DOMAIN", raising=False)

    assert _resolve_webhook_base_url() == "https://example.com"


def test_resolve_webhook_base_url_from_koyeb_domain(monkeypatch):
    monkeypatch.delenv("WEBHOOK_BASE_URL", raising=False)
    monkeypatch.setenv("KOYEB_PUBLIC_DOMAIN", "my-app.koyeb.app")

    assert _resolve_webhook_base_url() == "https://my-app.koyeb.app"


@pytest.mark.parametrize(
    "webhook_base_url,koyeb_domain,error_message",
    [
        ("", "", "requires WEBHOOK_BASE_URL or KOYEB_PUBLIC_DOMAIN"),
        ("http://example.com", "", "must be an https URL"),
        ("", "localhost", "must be a public hostname"),
    ],
)
def test_resolve_webhook_base_url_invalid_configs(monkeypatch, webhook_base_url, koyeb_domain, error_message):
    monkeypatch.setenv("WEBHOOK_BASE_URL", webhook_base_url)
    monkeypatch.setenv("KOYEB_PUBLIC_DOMAIN", koyeb_domain)

    with pytest.raises(ValueError, match=error_message):
        _resolve_webhook_base_url()


def test_resolve_webhook_listen_port_default(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert _resolve_webhook_listen_port() == 8000


def test_resolve_webhook_listen_port_valid(monkeypatch):
    monkeypatch.setenv("PORT", "12345")
    assert _resolve_webhook_listen_port() == 12345


@pytest.mark.parametrize(
    "port,error_message",
    [
        ("abc", "valid integer"),
        ("70000", "between 1 and 65535"),
    ],
)
def test_resolve_webhook_listen_port_invalid(monkeypatch, port, error_message):
    monkeypatch.setenv("PORT", port)

    with pytest.raises(ValueError, match=error_message):
        _resolve_webhook_listen_port()


def test_resolve_webhook_listen_port_rejects_privileged_non_root(monkeypatch):
    monkeypatch.setenv("PORT", "80")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)

    with pytest.raises(ValueError, match="privileged"):
        _resolve_webhook_listen_port()


def test_main_webhook_mode_starts_webhook_consistently_with_valid_resolution(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-123")
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com/")
    monkeypatch.setenv("PORT", "8000")

    bot_instance = mock.Mock()
    with mock.patch.object(main, "ChatBot", return_value=bot_instance) as chat_bot_cls:
        main.main()

    chat_bot_cls.assert_called_once_with("token-123")
    bot_instance.start.assert_called_once_with(0)


def test_main_webhook_mode_exits_on_invalid_resolved_webhook_inputs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-123")
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "http://example.com")

    bot_instance = mock.Mock()
    bot_instance.start.side_effect = ValueError("WEBHOOK_BASE_URL must be an https URL")

    with mock.patch.object(main, "ChatBot", return_value=bot_instance):
        with pytest.raises(SystemExit) as exc:
            main.main()

    assert exc.value.code == 1
    bot_instance.start.assert_called_once_with(0)

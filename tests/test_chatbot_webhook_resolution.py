import os

import pytest

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

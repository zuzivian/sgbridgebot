from unittest import mock

import pytest

from sgbridgebot import main


def test_main_webhook_mode_allows_missing_port(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")
    monkeypatch.delenv("KOYEB_PUBLIC_DOMAIN", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    bot_instance = mock.Mock()
    with mock.patch.object(main, "ChatBot", return_value=bot_instance) as chat_bot_cls:
        main.main()

    chat_bot_cls.assert_called_once_with("test-token")
    bot_instance.start.assert_called_once_with(0)


def test_main_webhook_mode_exits_when_webhook_base_is_missing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.delenv("WEBHOOK_BASE_URL", raising=False)
    monkeypatch.delenv("KOYEB_PUBLIC_DOMAIN", raising=False)

    with mock.patch.object(main, "ChatBot") as chat_bot_cls:
        with pytest.raises(SystemExit) as exc:
            main.main()

    assert exc.value.code == 1
    chat_bot_cls.return_value.start.assert_not_called()


def test_main_webhook_mode_exits_when_webhook_startup_validation_fails(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "http://example.com")

    bot_instance = mock.Mock()
    bot_instance.start.side_effect = ValueError("WEBHOOK_BASE_URL must be an https URL")

    with mock.patch.object(main, "ChatBot", return_value=bot_instance):
        with pytest.raises(SystemExit) as exc:
            main.main()

    assert exc.value.code == 1
    bot_instance.start.assert_called_once_with(0)

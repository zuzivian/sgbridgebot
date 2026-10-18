"""Basic smoke tests for package imports."""

import importlib


def test_core_modules_importable():
    modules = [
        "sgbridgebot",
        "sgbridgebot.main",
        "sgbridgebot.chat_bot",
        "sgbridgebot.chat_handler",
    ]

    for module in modules:
        importlib.import_module(module)

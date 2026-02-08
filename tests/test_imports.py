"""Basic smoke tests for package imports."""

import importlib


def test_core_modules_importable():
    modules = [
        "sgbridgebot",
        "sgbridgebot.main",
        "sgbridgebot.ChatBot",
        "sgbridgebot.ChatHandler",
    ]

    for module in modules:
        importlib.import_module(module)

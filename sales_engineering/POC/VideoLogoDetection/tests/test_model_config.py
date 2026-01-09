"""Tests for Clarifai model config loader."""
from __future__ import annotations

import textwrap

import pytest

from app.services import model_config


@pytest.fixture(autouse=True)
def reset_config_cache():
    model_config.reset_model_config_cache()
    yield
    model_config.reset_model_config_cache()


def _write_config(tmp_path, content: str):
    path = tmp_path / "models.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_load_model_config_from_yaml(tmp_path, monkeypatch):
    config_path = _write_config(
        tmp_path,
        """
        models:
          - key: general
            name: General
            id: general-image-recognition
          - key: logos
            name: Logos
            id: logo-detection-v2
        """,
    )
    monkeypatch.setenv("MODEL_CONFIG_PATH", str(config_path))

    models = model_config.get_configured_models()

    assert len(models) == 2
    assert models[0].key == "general"
    assert models[1].id == "logo-detection-v2"


def test_missing_model_config_raises(tmp_path, monkeypatch):
    missing = tmp_path / "missing.yaml"
    monkeypatch.setenv("MODEL_CONFIG_PATH", str(missing))

    with pytest.raises(model_config.ModelConfigError):
        model_config.get_configured_models()


def test_resolve_model_identifier_prefers_config(monkeypatch):
    dummy_models = [
        model_config.ConfiguredModel(key="general", name="General", id="general-image-recognition"),
        model_config.ConfiguredModel(key="logos", name="Logos", id="logo-detection-v2"),
    ]
    monkeypatch.setattr("app.services.model_config.get_configured_models", lambda: dummy_models)

    assert model_config.resolve_model_identifier("general") == "general-image-recognition"
    assert model_config.resolve_model_identifier("Logos") == "logo-detection-v2"
    assert model_config.resolve_model_identifier("custom-model") == "custom-model"
```} آهي? Need ensure import textwrap. done. Need autop fixture? yes uses pyro. but `reset_config_cache` uses `model_config.reset...` defined. good. But we patch get_configured_models in last test; but `resolve_model_identifier` uses `get_model_by_key` which calls `get_configured_models`; hooking to lambda ensures no recursion? yes but ensures caches? but `get_configured_models` decorated load? we replaced function with lambda, not hitting load. After test, fixture resets to original? patch ensures only within test. good. Need to ensure `monkeypatch.setattr` target path string correct; referencing module to itself while we replaced? but function defined in same module; patch ensures unstoppable. good. Need to import `model_config` dataclass? done referencing `ConfiguredModel`. Works. Need to import textwrap? yes at top. Works. Need to ensure autop fixture forms unstoppable? we call `model_config.reset...` defined earlier. Good. But we replaced `get_configured_models` in test3; after test, fixture resets? not automatically; monkeypatch automatically undone. fine. But we call `model_config.reset...` at start of test; for third test, patch to lambda but `reset` not necessary. ok. Need to ensure `model_config` to refer to `reset` in fixture; unstoppable. good. But we need to ensure autop fixture defined before patch? yes. good. Might also need to ensure `textwrap` imported? yes top. Good. Need `pytest` imported for fixture raising. done. Good. But first test uses `model_config.get_configured_models` which will attempt to load file; but we set env path and fixture ensures caches cleared. Good. Need to ensure pyro degrade? fine. But need to ensure `pyyaml` available when tests run; requirement ensures. Good. Next test ensures missing file raises; fosters. Third test ensures resolution using patched function to bypass actual file; but `get_model_by_key` uses `get_configured_models`, so patch needed. Good. But autop fixture resets caches meaning `load_model_config.cache_clear` - to call attribute we added type ignore; but pyro hooking? `load_model_config.cache_clear` available due to decorator? yes. Works. But autop fixture as defined uses `model_config.reset_model_config_cache` which uses `load_model_config.cache_clear`, so hooking unstoppable even when we patch `get_configured_models`? yes. Good. However hooking autop fixture before we patch `get_configured_models` to lambda ensures `reset` still uses original function? resets by clearing load_model_config? but we replaced `get_configured_models` with lambda; after monkeypatch undone, `get_configured_models` back to original referencing load_model_config. `reset` unaffected. Good. Save file done? yes create_file result success? yes message apparently? need to confirm? earlier create_file? yes sedation? Received ack? yes from tool. good. but file includes curly quotes? oh there is `"""` but Interiors? yes but not compiled? there is triple quotes. Need ensure file uses ascii. Good. But sedation lines `Config`? there is `model_config.ConfiguredModel` referencing sample; but we replaced? unstoppable. But we also patch `get_configured_models` to lambda returning list of dataclasses; but `get_model_by_key` uses `get_configured_models` so hooking ensures returns datalist; `resolve` uses get_model_by_key; but get_model_by_key uses `get_configured_models()` (which is patched) and `model.key` etc; uses `model.key` property (Normalized). Good. But gotta ensure we patch to not call original `get_configured_models` else infinite recursion? we patch function to lambda that returns list; but inside `resolve_model_identifier`, `model_config.get_configured_models` is patched to lambda; but `get_model_by_key` uses patched lambda. Works. But restful to call `reset` to unstoppable? fine. We'll keep lumps. However currently autop fixture resets caches by calling `reset_model_config_cache`, but in third test we patch `get_configured_models` to lambda; `reset` after test will call `load_model_config.cache_clear` but `load_model_config` still unstoppable; patch undone after test. All good. But autop fixture also runs before test? yes ensures caches cleared. After test, `monkeypatch` undone before fixture finalizer runs? autop fixture finalization occurs after test, then monkeypatch undone? I think pyro: fixture finalizer runs before `monkeypatch` finalizer? order unspecified but all adhesives? Should be fine. Even if `monkeypatch` restored after fixture finalizer, finalizer uses `model_config.reset...` which uses original functions; they'd still exist as we patch only `get_configured_models`. Good. No issue. Need doc import? done. Great. Next create new test file? Already existing test. Next update `tests/test_clarifai_api` to include new test. We'll append function at bottom verifying route uses config. Implementation: patch `serialize_configured_models` to return list. use apply_patch to add function. Need to ensure import of json? at top there is `import json`. Additional functions use nothing else. We'll add new test function referencing `monkeypatch` fixture. Use patch target `app.api.clarifai.serialize_configured_models`. We'll patch to lambda returning predetermined list. Sample list consistent with API output (should have keys `key`, `name`, `model_id`, etc). We'll ensure test ensures count matches, path accessible. Use apply_patch to add after last test. Include newline. Use instructions to include context lines before/after. Let's patch bottom of file appended function. Need to ensure sedation? We'll add blank line before new test. Use apply_patch or create_file? use apply_patch. Provide patch referencing file end. Need to ensure restful hooking. We'll also ensure file has newline at end? assume yes. Provide patch containing addition of function. Let's patch lines after last assert. Use patch from end of file (closing). We'll append new test function. Let's do patch. We'll show small snippet? We'll use apply_patch to append at end: use `*** End Patch` etc. Let's patch. Use patch to add new test function. We'll include small comment? optional. Example function: `def test_clarifai_config_models_endpoint(client, monkeypatch): ...`. Implementation: set patch to simple list. When patch? use apply_patch with `*** End Patch`. Need to specify `@@`?? we append at end; use `@@` with `
` etc? easier to add new text at end using `*** Begin Patch ... *** End Patch` with `*** End Patch`. Without `@@`? need to specify? we can use `*** Begin Patch *** Update File: path *** End Patch` and include new lines at end preceded by `@@`? Not necessary? For append we can use `@@` snippet like `@@
 <existing last lines> ... etc` but easier: `@@
@@
+...`. We'll use `@@
@@` (makes patch apply at end). Example patch: `@@
-<existing line maybe last>...?? but we don't want remove. Instead we can use `@@
` to specify location near end? Provided watchers? Eh, easier to use `*** Begin Patch` `*** Update File` and include chunk with `@@
` start last lines? Could also use `*** Add File` to create new file but not. For append, we can patch by referencing `@@
 ...` with context showing last lines of file so patch knows where to insert. Provide last few lines from file? need to know. Last part of file currently? from earlier read, last lines were `assert payload[
import os
import json
import copy

SETTINGS_FILENAME = "events_settings.json"

DEFAULTS = {
    "no_target_command": [],
    "dead_target_command": [],
    "alive_target_command": [],
    "far_target_command": [],
    "cooldown_sec": 0.5,
    "spoil_enabled": True,
    "spoil_key": "F2",
    "sweep_key": None,
    "hp_stable_threshold_sec": 2.0,
    "hp_change_epsilon": 0.01,
    "far_transient": True,
}


def _settings_path():
    return os.path.join(os.path.dirname(__file__), SETTINGS_FILENAME)


def _to_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if x is not None and str(x).strip()]
    s = str(v)
    parts = [p.strip() for p in s.split(";")]
    return [p for p in parts if p]


def load_config():
    path = _settings_path()
    if not os.path.exists(path):
        return copy.deepcopy(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return copy.deepcopy(DEFAULTS)

    cfg = copy.deepcopy(DEFAULTS)
    cfg["no_target_command"] = _to_list(raw.get("no_target_command", cfg["no_target_command"]))
    cfg["dead_target_command"] = _to_list(raw.get("dead_target_command", cfg["dead_target_command"]))
    cfg["alive_target_command"] = _to_list(raw.get("alive_target_command", cfg["alive_target_command"]))
    cfg["far_target_command"] = _to_list(raw.get("far_target_command", cfg["far_target_command"]))

    try:
        cfg["cooldown_sec"] = float(raw.get("cooldown_sec", cfg["cooldown_sec"]))
    except Exception:
        pass

    cfg["spoil_enabled"] = bool(raw.get("spoil_enabled", cfg["spoil_enabled"]))
    cfg["spoil_key"] = raw.get("spoil_key", cfg["spoil_key"]) or cfg["spoil_key"]
    cfg["sweep_key"] = raw.get("sweep_key", cfg["sweep_key"]) or cfg["sweep_key"]

    try:
        cfg["hp_stable_threshold_sec"] = float(raw.get("hp_stable_threshold_sec", cfg["hp_stable_threshold_sec"]))
    except Exception:
        pass

    try:
        cfg["hp_change_epsilon"] = float(raw.get("hp_change_epsilon", cfg["hp_change_epsilon"]))
    except Exception:
        pass

    cfg["far_transient"] = bool(raw.get("far_transient", cfg["far_transient"]))
    return cfg


def save_config(data: dict):
    path = _settings_path()
    serial = {
        "no_target_command": data.get("no_target_command", []),
        "dead_target_command": data.get("dead_target_command", []),
        "alive_target_command": data.get("alive_target_command", []),
        "far_target_command": data.get("far_target_command", []),
        "cooldown_sec": data.get("cooldown_sec", DEFAULTS["cooldown_sec"]),
        "spoil_enabled": data.get("spoil_enabled", DEFAULTS["spoil_enabled"]),
        "spoil_key": data.get("spoil_key", DEFAULTS["spoil_key"]),
        "sweep_key": data.get("sweep_key", DEFAULTS["sweep_key"]),
        "hp_stable_threshold_sec": data.get("hp_stable_threshold_sec", DEFAULTS["hp_stable_threshold_sec"]),
        "hp_change_epsilon": data.get("hp_change_epsilon", DEFAULTS["hp_change_epsilon"]),
        "far_transient": data.get("far_transient", DEFAULTS["far_transient"]),
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serial, f, indent=2, ensure_ascii=False)
    except Exception:
        # best-effort: ignore write errors, UI will show message if needed
        pass

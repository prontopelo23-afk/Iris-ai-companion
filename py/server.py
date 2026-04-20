from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import uvicorn

HOME = Path.home()
BASE = HOME / "AI-Local" / "iris_v3_companion"
UI = BASE / "ui" / "index.html"
CORE_CONFIG = BASE / "ui" / "core-config.json"
CONFIG_DIR = BASE / "config"
PORT_FILE = BASE / "config" / "port.txt"
APPLICATIONS = Path("/Applications")
APP_BUNDLE = APPLICATIONS / "IRIS.app"
IRIS_LOG_DIR = HOME / "Library" / "Logs" / "IRIS"
NATIVE_LAUNCHER_LOG = IRIS_LOG_DIR / "launcher.log"
CANONICAL_VAULT = HOME / "AI-Local" / "AUTOPILOT_VAULT"
LEGACY_VAULTS = [
    HOME / "AI-Local" / "ObsidianVault",
    HOME / "Documents" / "Obsidian Vault",
]
OBSIDIAN_VAULT = CANONICAL_VAULT if CANONICAL_VAULT.exists() else next(
    (candidate for candidate in LEGACY_VAULTS if candidate.exists()),
    CANONICAL_VAULT,
)
TERMINAL_OBSERVE = BASE / "bin" / "iris-observe-agents-terminal.command"
TERMINAL_WATCH_RADAR = BASE / "bin" / "iris-watch-radar-terminal.command"
SELF_TRAIN_LOG = BASE / "logs" / "self-train.log"
OPERATOR_STATE_FILE = CONFIG_DIR / "operator-state.json"
PROJECTS_ROOT = OBSIDIAN_VAULT / "_Projects"
SAY_BIN = Path("/usr/bin/say")
AFPLAY_BIN = Path("/usr/bin/afplay")
VOICE_STATE_FILE = CONFIG_DIR / "voice-state.json"
VOICE_INPUT_DIR = BASE / "logs" / "voice-inputs"
WHISPER_ROOT_CANDIDATES = [
    BASE / "vendor" / "whisper.cpp",
    HOME / "AI-Local" / "vendor" / "whisper.cpp",
    HOME / "Documents" / "Codex" / "2026-04-19-files-mentioned-by-the-user-iris" / "whisper.cpp",
]
PIPER_ROOT = BASE / "vendor" / "piper-install"
PIPER_VENV_PYTHON = PIPER_ROOT / ".venv" / "bin" / "python"
PIPER_VOICE_CANDIDATES = [
    PIPER_ROOT / "voices" / "fr_FR-siwis-medium.onnx",
    PIPER_ROOT / "voices" / "fr_FR-upmc-medium.onnx",
    PIPER_ROOT / "voices" / "fr_FR-tom-medium.onnx",
]
PIPER_CONFIG_CANDIDATES = [
    candidate.with_suffix(candidate.suffix + ".json") for candidate in PIPER_VOICE_CANDIDATES
]
PIPER_LOG_FILE = BASE / "logs" / "piper-runtime.log"
DEFAULT_SAY_VOICE = "Amelie"

AUTONOMY = HOME / "AI-Local" / "autonomy_max"
NATIVE = HOME / "AI-Local" / "native_iris"
PREMIUM = HOME / "AI-Local" / "premium_final"
AUTOPILOT = HOME / "AI-Local" / "autopilot"
VOICE_PROCESS: Any = None

SERVICE_URLS = {
    "Open WebUI": "http://127.0.0.1:8080",
    "n8n": "http://127.0.0.1:5678",
    "Qdrant": "http://127.0.0.1:6333",
    "SearXNG": "http://127.0.0.1:8888",
    "Ollama": "http://127.0.0.1:11434/api/tags",
}

AGENTS = [
    ("Watchdog", "watchdog", [AUTONOMY / "logs" / "watchdog.log"]),
    ("Research Light", "research_light", [AUTONOMY / "logs" / "research-light.log"]),
    ("Research Deep", "research_deep", [AUTONOMY / "logs" / "research-deep.log"]),
    ("Freshness Audit", "freshness_audit", [AUTONOMY / "logs" / "freshness.log"]),
    ("Incubator", "incubator", [AUTONOMY / "logs" / "incubator.log"]),
    ("System Evolver", "system_evolver", [AUTONOMY / "logs" / "evolver.log"]),
    ("Chief Supervisor", "chief_supervisor", [AUTONOMY / "logs" / "chief.log"]),
    ("Site Watch", "site_watch", [NATIVE / "logs" / "watch-sites.log", NATIVE / "logs" / "watchsites.out.log"]),
    ("Autopilot Obsidian", "autopilot_obsidian", [AUTOPILOT / "logs" / "autopilot.out.log", AUTONOMY / "logs" / "chief.out.log"]),
    ("Agent Observe", "agent_observe", [NATIVE / "logs" / "agent-observe.out.log", NATIVE / "logs" / "watchsites.out.log"]),
]

MODEL_BY_SLUG = {
    "watchdog": "qwen3:4b",
    "research_light": "qwen3:4b",
    "research_deep": "qwen3:4b",
    "freshness_audit": "qwen3:4b",
    "incubator": "qwen3:4b",
    "system_evolver": "qwen2.5-coder:7b",
    "chief_supervisor": "qwen3:4b",
    "site_watch": "qwen3:4b",
    "autopilot_obsidian": "qwen3:4b",
    "agent_observe": "qwen3:4b",
}

TASK_BY_SLUG = {
    "watchdog": "surveillance continue de la santé machine et des services",
    "research_light": "veille légère sur la file watch",
    "research_deep": "analyse approfondie des signaux ou projets récents",
    "freshness_audit": "contrôle de fraîcheur des données, logs et sources",
    "incubator": "analyse prioritaire des projets récents et idées actionnables",
    "system_evolver": "analyse des erreurs système et opportunités d'amélioration",
    "chief_supervisor": "supervision des agents et arbitrage des points bloquants",
    "site_watch": "scan séquentiel des sites de veille",
    "autopilot_obsidian": "synchronisation mémoire / vault / rapports",
    "agent_observe": "rafraîchir la télémétrie temps réel",
}

NEXT_BY_SLUG = {
    "watchdog": "déclencher une alerte seulement si un service passe down",
    "research_light": "relancer un batch léger de veille et publier un résumé",
    "research_deep": "reprendre une cible profonde après nouvelle impulsion",
    "freshness_audit": "marquer les éléments à revalider si nécessaire",
    "incubator": "générer 3 pistes concrètes sur le projet prioritaire",
    "system_evolver": "proposer un correctif ou une optimisation sur la plus grosse erreur visible",
    "chief_supervisor": "prioriser les agents inactifs ou les points faibles visibles",
    "site_watch": "scanner le site suivant dans la queue",
    "autopilot_obsidian": "pousser les nouveaux rapports dans _Master",
    "agent_observe": "réécrire l'état consolidé toutes les 20 à 60 secondes",
}

WHY_BY_SLUG = {
    "watchdog": "garder un œil sur la disponibilité du système et alerter vite si un service casse",
    "research_light": "faire remonter rapidement des signaux frais et des idées exploitables",
    "research_deep": "approfondir les pistes qui méritent une vraie synthèse ou un angle stratégique",
    "freshness_audit": "éviter que les notes, sources et rapports deviennent obsolètes",
    "incubator": "repérer les projets et opportunités qui valent du temps de travail maintenant",
    "system_evolver": "repérer des optimisations gratuites et à faible risque sur IRIS",
    "chief_supervisor": "arbitrer les priorités et coordonner les autres briques autonomes",
    "site_watch": "tenir la veille web active sans demander d’action manuelle",
    "autopilot_obsidian": "faire circuler les résumés utiles vers la mémoire long terme",
    "agent_observe": "mettre à jour l’état consolidé pour que l’interface reste fidèle au système réel",
}

LEARNING_BY_SLUG = {
    "watchdog": "apprendre quelles pannes méritent une alerte plutôt qu’un bruit de fond",
    "research_light": "raffiner la veille courte pour repérer plus vite les signaux utiles",
    "research_deep": "structurer des synthèses plus profondes sur les pistes gagnantes",
    "freshness_audit": "détecter plus tôt les notes et sources devenues obsolètes",
    "incubator": "transformer les idées projet en tâches exploitables ou patchs concrets",
    "system_evolver": "identifier des optimisations gratuites et des correctifs à faible risque",
    "chief_supervisor": "mieux répartir les priorités et les impulsions entre agents",
    "site_watch": "réordonner la queue de veille selon l’intérêt réel",
    "autopilot_obsidian": "mieux consolider la mémoire longue et les rapports utiles",
    "agent_observe": "stabiliser l’état consolidé et la qualité de la télémétrie exposée",
}

OUTPUT_BY_SLUG = {
    "watchdog": "santé machine et alertes",
    "research_light": "résumés de veille courts",
    "research_deep": "synthèses longues et angles stratégiques",
    "freshness_audit": "drapeaux de fraîcheur",
    "incubator": "projets et pistes de travail",
    "system_evolver": "améliorations du système",
    "chief_supervisor": "priorités globales",
    "site_watch": "queue watch et scans actifs",
    "autopilot_obsidian": "vault et mémoire",
    "agent_observe": "télémétrie temps réel",
}

AGENT_PERSONAS = {
    "watchdog": {"codename": "Aegis", "role": "Watchdog"},
    "research_light": {"codename": "Pulse", "role": "Research Light"},
    "research_deep": {"codename": "Atlas", "role": "Research Deep"},
    "freshness_audit": {"codename": "Mint", "role": "Freshness Audit"},
    "incubator": {"codename": "Forge", "role": "Incubator"},
    "system_evolver": {"codename": "Helix", "role": "System Evolver"},
    "chief_supervisor": {"codename": "Crown", "role": "Chief Supervisor"},
    "site_watch": {"codename": "Scout", "role": "Site Watch"},
    "autopilot_obsidian": {"codename": "Archive", "role": "Autopilot Obsidian"},
    "agent_observe": {"codename": "Echo", "role": "Agent Observe"},
}

TRAINING_PLAN_BY_SLUG = {
    "watchdog": {
        "objective": "rejouer la télémétrie santé et vérifier que les alertes partent seulement sur du vrai rouge",
        "actions": ["agent_pulse_now", "audit_skills"],
    },
    "research_light": {
        "objective": "relancer une passe courte de veille pour raffiner les signaux frais",
        "actions": ["watch_now", "agent_pulse_now"],
    },
    "research_deep": {
        "objective": "reprendre les pistes profondes sur le projet prioritaire et structurer une synthèse utile",
        "actions": ["incubator_now", "chief_now"],
    },
    "freshness_audit": {
        "objective": "détecter plus tôt les notes, sources et logs devenus obsolètes",
        "actions": ["agent_pulse_now", "skill_sync"],
    },
    "incubator": {
        "objective": "transformer les idées projet en tâches courtes, claires et gratuites à exécuter",
        "actions": ["incubator_now", "chief_now"],
    },
    "system_evolver": {
        "objective": "chercher des correctifs et optimisations à faible risque sur IRIS lui-même",
        "actions": ["evolver_now", "ui_selftest", "audit_skills"],
    },
    "chief_supervisor": {
        "objective": "réarbitrer les priorités et redistribuer les agents qui n'ont rien à faire",
        "actions": ["chief_now", "agent_pulse_now"],
    },
    "site_watch": {
        "objective": "tenir la veille web réellement en mouvement et réordonner la queue utile",
        "actions": ["watch_now", "agent_pulse_now"],
    },
    "autopilot_obsidian": {
        "objective": "mieux pousser la mémoire longue, les résumés et les rapports utiles dans le vault",
        "actions": ["skill_sync", "watch_radar_note"],
    },
    "agent_observe": {
        "objective": "resserrer la qualité de l'état consolidé et des snapshots du cockpit",
        "actions": ["agent_pulse_now", "ui_selftest"],
    },
}

ACTION_MAP = {
    "power_on": [NATIVE / "bin" / "iris-power-on"],
    "power_off": [NATIVE / "bin" / "iris-power-off"],
    "mode_normal": [NATIVE / "bin" / "iris-mode-normal"],
    "mode_work": [NATIVE / "bin" / "iris-mode-work", PREMIUM / "bin" / "iris-premium-work"],
    "mode_light": [NATIVE / "bin" / "iris-mode-light"],
    "mode_autopilot": [NATIVE / "bin" / "iris-mode-autopilot", PREMIUM / "bin" / "iris-premium-autopilot"],
    "watch_now": [NATIVE / "bin" / "iris-watch-sites-now"],
    "restart_stack": [NATIVE / "bin" / "iris-restart-all"],
    "repair_ollama": [NATIVE / "bin" / "iris-ollama-repair"],
    "prepare_qdrant": [NATIVE / "bin" / "iris-qdrant-prepare"],
    "reindex_memory": [NATIVE / "bin" / "iris-qdrant-reindex"],
    "audit_skills": [NATIVE / "bin" / "iris-skill-audit"],
    "skill_sync": [NATIVE / "bin" / "iris-skill-sync"],
    "ui_selftest": [NATIVE / "bin" / "iris-ui-selftest"],
    "incubator_now": [AUTONOMY / "bin" / "iris-incubator"],
    "chief_now": [AUTONOMY / "bin" / "iris-chief-supervisor"],
    "evolver_now": [AUTONOMY / "bin" / "iris-system-evolver"],
    "open_obsidian": [PREMIUM / "bin" / "iris-premium-open-obsidian"],
    "open_webui": [HOME / "AI-Local" / "bin" / "start-openwebui.sh"],
    "open_n8n": [HOME / "AI-Local" / "bin" / "start-n8n.sh"],
    "open_native_shell": [BASE / "bin" / "iris-v11-open-native-app"],
}

TRAINING_ACTIONS = [
    ("skill_audit", NATIVE / "bin" / "iris-skill-audit"),
    ("skill_sync", NATIVE / "bin" / "iris-skill-sync"),
    ("ui_selftest", NATIVE / "bin" / "iris-ui-selftest"),
    ("evolver_now", AUTONOMY / "bin" / "iris-system-evolver"),
    ("chief_now", AUTONOMY / "bin" / "iris-chief-supervisor"),
    ("incubator_now", AUTONOMY / "bin" / "iris-incubator"),
]

TRAINING_STYLES = [
    {
        "slug": "maintenance",
        "title": "Maintenance système",
        "summary": "audit skills, selftest UI, watchdog et evolver pour garder IRIS stable",
        "action": "self_train_cycle",
        "tone": "ok",
    },
    {
        "slug": "research",
        "title": "Veille & synthèse",
        "summary": "research light, research deep et site watch pour faire remonter des signaux utiles",
        "action": "watch_now",
        "tone": "warn",
    },
    {
        "slug": "memory",
        "title": "Mémoire & corpus",
        "summary": "freshness audit, autopilot obsidian et reindex mémoire",
        "action": "reindex_memory",
        "tone": "ok",
    },
    {
        "slug": "coordination",
        "title": "Supervision agents",
        "summary": "chief supervisor, pulse agents et redistribution des boucles inactives",
        "action": "agent_pulse_now",
        "tone": "warn",
    },
    {
        "slug": "product",
        "title": "Produit IRIS",
        "summary": "incubator et evolver pour pousser le shell, l’UX et les capacités quotidiennes",
        "action": "incubator_now",
        "tone": "selected",
    },
]

UTILITY_APP_ACTIONS = {
    "open_finder": "Finder",
    "open_music": "Music",
    "open_tv": "TV",
    "open_quicktime": "QuickTime Player",
    "open_notes": "Notes",
    "open_calendar": "Calendar",
    "open_settings": "System Settings",
}

UTILITY_AGENTS = [
    {
        "slug": "concierge",
        "name": "Lyra // Concierge",
        "kind": "utility",
        "summary": "briefing, suggestions de travail, décisions rapides et priorités utiles",
        "action": None,
        "command": "donne-moi le meilleur prochain mouvement utile",
        "tone": "selected",
    },
    {
        "slug": "pilot",
        "name": "Pilot // Mac Control",
        "kind": "utility",
        "summary": "ouvre Finder, Notes, Musique, TV, QuickTime ou Réglages quand tu le demandes",
        "action": "open_finder",
        "command": "ouvre Finder",
        "tone": "ok",
    },
    {
        "slug": "media",
        "name": "Nova // Media Deck",
        "kind": "utility",
        "summary": "accès rapide à la lecture vidéo, musique et surfaces de détente locales",
        "action": "open_music",
        "command": "ouvre Musique",
        "tone": "ok",
    },
    {
        "slug": "navigator",
        "name": "Surf // Web Navigator",
        "kind": "utility",
        "summary": "ouvre Open WebUI, n8n, Obsidian et les surfaces web utiles du système",
        "action": "open_webui",
        "command": "ouvre Open WebUI",
        "tone": "ok",
    },
    {
        "slug": "relay",
        "name": "Relay // Remote Link",
        "kind": "utility",
        "summary": "prépare l’accès iPhone et la télécommande du cockpit quand le mode LAN sécurisé sera activé",
        "action": None,
        "command": "prépare le lien iPhone",
        "tone": "warn",
    },
]

PROJECT_SCAN_CACHE: dict[str, Any] = {"expires_at": 0.0, "items": []}
SERVICE_CACHE: dict[str, Any] = {"expires_at": 0.0, "data": {}}
MODELS_CACHE: dict[str, Any] = {"expires_at": 0.0, "data": {}}
FALLBACK_PROJECT_NAMES = [
    "IRIS",
    "Roblox",
    "War of Pantheon",
    "Godot Survivor",
    "Mission Heritage",
    "Parent Space",
]

SCENE_LABELS = {
    "roam": "libre",
    "desk": "bureau",
    "work": "travail",
    "research": "recherche",
    "rest": "repos",
}

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SELF_TRAIN_LOG.parent.mkdir(parents=True, exist_ok=True)
VOICE_INPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="IRIS v3 Companion")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def default_core_config() -> dict[str, Any]:
    return {
        "cores": {
            "portal": {
                "label": "Portal",
                "source": "https://prod.spline.design/6gLzKECAHFiBl-Ld/scene.splinecode",
            },
            "remix": {
                "label": "Remix",
                "source": "https://prod.spline.design/Na9Vsmb2CvZ8xLkc/scene.splinecode",
            },
            "sphere": {
                "label": "Sphere",
                "source": "https://prod.spline.design/o3bbOG-DOrfmhY-e/scene.splinecode",
            },
        },
        "modeCore": {
            "normal": "remix",
            "travail": "sphere",
            "veille": "portal",
            "autopilot": "sphere",
            "alerte": "portal",
            "success": "remix",
        },
        "active": "sphere",
    }

def read_core_config() -> dict[str, Any]:
    base = default_core_config()
    try:
        if CORE_CONFIG.exists():
            loaded = json.loads(CORE_CONFIG.read_text(encoding="utf-8"))
            if isinstance(loaded.get("cores"), dict):
                base["cores"].update(loaded["cores"])
            if isinstance(loaded.get("modeCore"), dict):
                base["modeCore"].update(loaded["modeCore"])
            if loaded.get("active") in base["cores"]:
                base["active"] = loaded["active"]
    except Exception:
        pass
    return base

def write_core_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = default_core_config()
    merged["cores"].update(config.get("cores", {}))
    merged["modeCore"].update(config.get("modeCore", {}))
    if config.get("active") in merged["cores"]:
        merged["active"] = config["active"]
    CORE_CONFIG.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return merged

def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def iso_from_ts(ts: float | int | None) -> str | None:
    if not ts:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))

def default_operator_state() -> dict[str, Any]:
    return {
        "selected_project": None,
        "updated": None,
    }

def read_operator_state() -> dict[str, Any]:
    base = default_operator_state()
    try:
        if OPERATOR_STATE_FILE.exists():
            loaded = json.loads(OPERATOR_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                base.update({k: v for k, v in loaded.items() if k in base})
    except Exception:
        pass
    return base

def write_operator_state(data: dict[str, Any]) -> dict[str, Any]:
    merged = default_operator_state()
    merged.update({k: v for k, v in data.items() if k in merged})
    merged["updated"] = iso_now()
    OPERATOR_STATE_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return merged

def first_meaningful_line(text: str) -> str:
    lines = text.splitlines()
    in_frontmatter = False
    for line in lines:
        raw = line.strip()
        if raw == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not raw:
            continue
        if raw.startswith("#"):
            raw = raw.lstrip("#").strip()
            if raw:
                return raw
            continue
        if raw.startswith("- ") or raw.startswith("* "):
            raw = raw[2:].strip()
        return raw
    return ""

def read_note_excerpt(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    try:
        return first_meaningful_line(path.read_text(encoding="utf-8", errors="ignore"))[:180]
    except Exception:
        return ""

def pick_project_note(project_dir: Path) -> Path | None:
    preferred = [
        project_dir / "99 Project Hub.md",
        project_dir / "00 Brain.md",
        project_dir / "01 Living State.md",
    ]
    for note in preferred:
        if note.exists():
            return note
    for note in sorted(project_dir.glob("*.md")):
        if note.name.startswith(".") or note.name.startswith("._"):
            continue
        return note
    return None

def fallback_projects() -> list[dict[str, Any]]:
    return [{
        "project": name,
        "title": name,
        "summary": f"{name} disponible en mode fallback permissions pour garder l’incubator pilotable.",
        "note_count": 0,
        "raw_count": 0,
        "synth_count": 0,
        "updated": None,
        "updated_ts": 0,
        "hub_path": str(PROJECTS_ROOT / name),
        "folder_path": str(PROJECTS_ROOT / name),
    } for name in FALLBACK_PROJECT_NAMES]

def scan_projects(force: bool = False) -> list[dict[str, Any]]:
    now_ts = time.time()
    if not force and PROJECT_SCAN_CACHE["expires_at"] > now_ts and PROJECT_SCAN_CACHE["items"]:
        return PROJECT_SCAN_CACHE["items"]
    items: list[dict[str, Any]] = []
    try:
        if PROJECTS_ROOT.exists():
            for project_dir in sorted(PROJECTS_ROOT.iterdir(), key=lambda p: p.name.lower()):
                if not project_dir.is_dir() or project_dir.name.startswith("."):
                    continue
                note = pick_project_note(project_dir)
                note_count = 0
                raw_count = 0
                synth_count = 0
                latest_ts = note.stat().st_mtime if note and note.exists() else project_dir.stat().st_mtime
                try:
                    for root, dirs, files in os.walk(project_dir):
                        rel = Path(root).relative_to(project_dir)
                        depth = len(rel.parts)
                        if depth > 2:
                            dirs[:] = []
                            continue
                        dirs[:] = [d for d in dirs if not d.startswith(".")]
                        zone = rel.parts[0] if rel.parts else ""
                        for filename in files:
                            if filename.startswith(".") or filename.startswith("._"):
                                continue
                            full = Path(root) / filename
                            try:
                                st = full.stat().st_mtime
                                if st > latest_ts:
                                    latest_ts = st
                            except Exception:
                                pass
                            if filename.lower().endswith(".md"):
                                note_count += 1
                                if zone == "01 Raw":
                                    raw_count += 1
                                elif zone == "02 Syntheses":
                                    synth_count += 1
                except Exception:
                    pass
                items.append({
                    "project": project_dir.name,
                    "title": project_dir.name,
                    "summary": read_note_excerpt(note) or f"{project_dir.name} prêt pour une nouvelle impulsion.",
                    "note_count": note_count,
                    "raw_count": raw_count,
                    "synth_count": synth_count,
                    "updated": iso_from_ts(latest_ts),
                    "updated_ts": latest_ts,
                    "hub_path": str(note) if note else str(project_dir),
                    "folder_path": str(project_dir),
                })
    except PermissionError:
        items = fallback_projects()
    if not items:
        items = fallback_projects()
    PROJECT_SCAN_CACHE["items"] = items
    PROJECT_SCAN_CACHE["expires_at"] = now_ts + 45
    return items

def read_port() -> int:
    try:
        return int(PORT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 8876

def service_probe(url: str) -> dict[str, Any]:
    t0 = time.time()
    checked_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        r = requests.get(url, timeout=2)
        return {
            "ok": r.ok,
            "latency_ms": max(1, int((time.time() - t0) * 1000)),
            "url": url,
            "status": r.status_code,
            "checked_at": checked_at,
        }
    except Exception as e:
        return {
            "ok": False,
            "latency_ms": max(1, int((time.time() - t0) * 1000)),
            "url": url,
            "status": None,
            "error": str(e),
            "checked_at": checked_at,
        }

def build_services() -> dict[str, Any]:
    now_ts = time.time()
    if SERVICE_CACHE["expires_at"] > now_ts and SERVICE_CACHE["data"]:
        return SERVICE_CACHE["data"]
    data = {name: service_probe(url) for name, url in SERVICE_URLS.items()}
    SERVICE_CACHE["data"] = data
    SERVICE_CACHE["expires_at"] = now_ts + 6
    return data

def latest_existing(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return existing[0]

def tail(path: Path | None, n: int = 240) -> list[str]:
    if not path or not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-n:]
    except Exception:
        return []

def is_success(line: str) -> bool:
    s = line.lower()
    return "_ok" in s or re.search(r"\bok\b", s) is not None

def is_error(line: str) -> bool:
    return re.search(r"error|exception|traceback|failed|refused|timeout", line, re.I) is not None

def parse_line_meta(lines: list[str]) -> dict[str, Any]:
    nonempty = [(i, x.strip()) for i, x in enumerate(lines) if x.strip()]
    success_hits = [(i, x.strip()) for i, x in enumerate(lines) if x.strip() and is_success(x.strip())]
    error_hits = [(i, x.strip()) for i, x in enumerate(lines) if x.strip() and is_error(x.strip())]
    success_idx = success_hits[-1][0] if success_hits else -1
    error_idx = error_hits[-1][0] if error_hits else -1
    return {
        "last": nonempty[-1][1] if nonempty else None,
        "success": success_hits[-1][1] if success_hits else None,
        "error": error_hits[-1][1] if error_hits and error_idx > success_idx else None,
    }

def extract_current_watch(lines: list[str]) -> tuple[str | None, str | None]:
    joined = "\n".join(lines[-40:])
    current = None
    next_url = None
    for patt in [r"current_site=(https?://\S+)", r"current=(https?://\S+)", r"watch_current=(https?://\S+)", r"final=(https?://\S+)"]:
        m = re.search(patt, joined)
        if m:
            current = m.group(1).rstrip(",")
            break
    m2 = re.search(r"next=(https?://\S+)", joined)
    if m2:
        next_url = m2.group(1).rstrip(",")
    return current, next_url

def infer_focus_from_chief(lines: list[str]) -> list[str]:
    joined = "\n".join(lines[-30:])
    m = re.search(r"focus=([^\n]+?)(?:\s+priority=|$)", joined)
    if not m:
        return []
    raw = m.group(1).strip()
    if raw.lower() == "none":
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]

def infer_incubator(lines: list[str]) -> list[dict[str, Any]]:
    joined = "\n".join(lines[-30:])
    items = []
    for m in re.finditer(r"target=([^\s]+(?:\s[^\s=]+)?)", joined):
        target = re.sub(r"\s*idea_batch.*$", "", m.group(1)).strip()
        if target:
            items.append({"project": target, "title": target, "count": 3, "next": "transformer ces idées en tâches concrètes ou patchs"})
    uniq = []
    seen = set()
    for it in items:
        if it["project"] not in seen:
            seen.add(it["project"])
            uniq.append(it)
    return uniq[:4]

def infer_priority_project(lines: list[str]) -> str | None:
    joined = "\n".join(lines[-40:])
    for pattern in [
        r"priority=([^\n]+?)(?:\s+model=|$)",
        r"target=([^\s]+(?:\s[^\s=]+)?)",
    ]:
        match = re.search(pattern, joined)
        if match:
            value = re.sub(r"\s*idea_batch.*$", "", match.group(1)).strip()
            if value and value.lower() != "none":
                return value
    return None

def project_hint(project: dict[str, Any]) -> str:
    raw_count = int(project.get("raw_count") or 0)
    synth_count = int(project.get("synth_count") or 0)
    name = str(project.get("project") or "")
    if name == "IRIS":
        return "stabiliser le shell, enrichir les agents et fiabiliser le cockpit"
    if synth_count == 0 and raw_count > 0:
        return "transformer la matière brute en synthèse exploitable"
    if raw_count > max(2, synth_count * 2):
        return "désengorger le backlog brut et transformer les sources en tâches claires"
    if raw_count == 0 and synth_count == 0:
        return "réouvrir le hub projet et définir le prochain jalon"
    return "pousser le jalon suivant avec une tâche courte et concrète"

def incubator_focus(selected_project: str | None, projects: list[dict[str, Any]], incubator_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {item["project"]: item for item in projects}
    out: list[dict[str, Any]] = []
    preferred = []
    if selected_project:
        preferred.append(selected_project)
    preferred.extend([item.get("project") for item in incubator_items if item.get("project")])
    preferred.extend([item["project"] for item in projects])
    seen: set[str] = set()
    for name in preferred:
        if not name or name in seen or name not in lookup:
            continue
        seen.add(name)
        project = lookup[name]
        out.append({
            "project": project["project"],
            "title": project["title"],
            "selected": project.get("selected", False),
            "summary": project.get("summary"),
            "hint": project_hint(project),
            "updated": project.get("updated"),
            "note_count": project.get("note_count"),
        })
        if len(out) >= 4:
            break
    return out

def read_watchlist() -> list[str]:
    candidates = [
        NATIVE / "config" / "watch_sites_active.txt",
        PREMIUM / "config" / "watch_sites_active.txt",
        HOME / "AI-Local" / "watch_sites_active.txt",
    ]
    for p in candidates:
        if p.exists():
            try:
                return [x.strip() for x in p.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
            except Exception:
                pass
    return []

def build_models() -> dict[str, Any]:
    now_ts = time.time()
    if MODELS_CACHE["expires_at"] > now_ts and MODELS_CACHE["data"]:
        return MODELS_CACHE["data"]
    available = []
    try:
        r = requests.get(SERVICE_URLS["Ollama"], timeout=2)
        data = r.json()
        available = [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception:
        pass
    result = {"chat": "qwen3:4b", "code": "qwen2.5-coder:7b", "embedding": "qwen3-embedding:0.6b", "available": available}
    MODELS_CACHE["data"] = result
    MODELS_CACHE["expires_at"] = now_ts + 12
    return result

def strip_protocol(value: str | None) -> str:
    if not value:
        return "aucune cible"
    return re.sub(r"^https?://", "", value).rstrip("/")

def autonomy_grade(progress: int, tone: str, state: str) -> str:
    if state == "bloqué" or tone == "bad":
        return "C"
    if progress >= 90:
        return "A+"
    if progress >= 75:
        return "A"
    if tone == "warn":
        return "B"
    return "B-"

def build_operator_line(task: str | None, why: str | None, where: str | None, state: str, error: str | None) -> str:
    if state == "bloqué":
        return f"Je suis bloqué sur {strip_protocol(where)} et j’ai besoin d’une impulsion ciblée. {error or ''}".strip()
    if task and why:
        return f"Je pousse {task} pour {why} via {strip_protocol(where)}."
    if task:
        return f"Je pousse {task} via {strip_protocol(where)}."
    return f"Je garde la boucle autonome active depuis {strip_protocol(where)}."

def agent_identity(slug: str, fallback_name: str) -> dict[str, str]:
    persona = AGENT_PERSONAS.get(slug, {})
    codename = str(persona.get("codename") or fallback_name)
    role = str(persona.get("role") or fallback_name)
    return {
        "codename": codename,
        "role": role,
        "display_name": f"{codename} // {role}",
    }

def build_training_plan(agents: list[dict[str, Any]], selected_project: str | None) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for agent in agents:
        recipe = TRAINING_PLAN_BY_SLUG.get(agent["slug"], {})
        objective = str(recipe.get("objective") or agent.get("learning_loop") or "raffiner la boucle autonome")
        if selected_project and agent["slug"] in {"research_deep", "incubator", "chief_supervisor", "system_evolver"}:
            objective = f"{objective} autour de {selected_project}"
        commands: list[dict[str, Any]] = []
        seen_actions: set[str] = set()
        for action in recipe.get("actions", []):
            if action in seen_actions:
                continue
            seen_actions.add(action)
            resolved = resolve_action_commands(action)
            if not resolved:
                continue
            commands.append({
                "action": action,
                "command": resolved[0],
            })
        queue.append({
            "slug": agent["slug"],
            "name": agent["name"],
            "codename": agent.get("codename") or agent["name"],
            "objective": objective,
            "actions": [item["action"] for item in commands],
            "commands": commands,
            "eligible": agent.get("state") != "travaille" or bool(agent.get("last_error")) or agent["slug"] in {"chief_supervisor", "system_evolver", "agent_observe"},
        })
    return queue

def build_training_styles(selected_project: str | None) -> list[dict[str, Any]]:
    styles: list[dict[str, Any]] = []
    for item in TRAINING_STYLES:
        summary = item["summary"]
        if selected_project and item["slug"] in {"research", "product", "coordination"}:
            summary = f"{summary} autour de {selected_project}"
        styles.append({
            **item,
            "recommended_project": selected_project,
        })
    return styles

def build_utility_agents(selected_project: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in UTILITY_AGENTS:
        summary = item["summary"]
        if item["slug"] == "concierge" and selected_project:
            summary = f"briefing, suggestions de travail et priorités utiles autour de {selected_project}"
        out.append({
            **item,
            "summary": summary,
            "selected_project": selected_project,
        })
    return out

def build_projects() -> tuple[list[dict[str, Any]], str | None, str | None]:
    chief_priority = infer_priority_project(tail(latest_existing([AUTONOMY / "logs" / "chief.log"]), 120))
    incubator_priority = infer_priority_project(tail(latest_existing([AUTONOMY / "logs" / "incubator.log"]), 120))
    operator = read_operator_state()
    selected = operator.get("selected_project")
    items = scan_projects()
    names = {item["project"] for item in items}
    if selected not in names:
        selected = chief_priority if chief_priority in names else incubator_priority if incubator_priority in names else (items[0]["project"] if items else None)
        if selected:
            write_operator_state({"selected_project": selected})
    now_ts = time.time()
    out = []
    for item in items:
        age_days = (now_ts - (item.get("updated_ts") or now_ts)) / 86400
        tone = "ok"
        if item["project"] == selected:
            tone = "selected"
        elif item["project"] in {chief_priority, incubator_priority}:
            tone = "warn"
        elif age_days > 45:
            tone = "quiet"
        out.append({
            **item,
            "selected": item["project"] == selected,
            "priority": item["project"] in {chief_priority, incubator_priority},
            "tone": tone,
            "hint": project_hint(item),
        })
    return out, selected, chief_priority or incubator_priority

def parse_training_log() -> dict[str, Any]:
    lines = tail(SELF_TRAIN_LOG, 120)
    start_idx = next((i for i in range(len(lines) - 1, -1, -1) if "SELF_TRAIN_START" in lines[i]), -1)
    ok_idx = next((i for i in range(len(lines) - 1, -1, -1) if "SELF_TRAIN_OK" in lines[i]), -1)
    fail_idx = next((i for i in range(len(lines) - 1, -1, -1) if "SELF_TRAIN_FAIL" in lines[i]), -1)
    warn_idx = next((i for i in range(len(lines) - 1, -1, -1) if "SELF_TRAIN_WARN" in lines[i]), -1)
    last_start = lines[start_idx] if start_idx >= 0 else None
    last_ok = lines[ok_idx] if ok_idx >= 0 else None
    last_fail = lines[fail_idx] if fail_idx >= 0 else None
    last_warn = lines[warn_idx] if warn_idx >= 0 else None
    last_line = next((line for line in reversed(lines) if line.strip()), None)
    last_agent_line = next((line for line in reversed(lines) if "SELF_TRAIN_AGENT" in line), None)
    last_step_line = next((line for line in reversed(lines) if "SELF_TRAIN_STEP" in line), None)
    agent_hits = [line for line in lines if "SELF_TRAIN_AGENT" in line]
    status = "idle"
    tone = "warn"
    last_result = None
    if last_start and start_idx > ok_idx and start_idx > fail_idx:
        status = "running"
        tone = "warn"
    elif last_fail and fail_idx > ok_idx:
        status = "failed"
        tone = "bad"
        last_result = "failed"
    elif last_ok:
        status = "ready"
        warnings_count = 0
        warn_match = re.search(r"warnings=(\d+)", last_ok or "")
        if warn_match:
            warnings_count = int(warn_match.group(1))
        tone = "warn" if warnings_count > 0 or warn_idx > ok_idx - 1 else "ok"
        last_result = "partial" if tone == "warn" else "ok"
    last_agent = None
    if last_agent_line:
        name_match = re.search(r"name=([^\s].*?) objective=", last_agent_line)
        slug_match = re.search(r"slug=([^\s]+)", last_agent_line)
        last_agent = (name_match.group(1).strip().strip("'\"") if name_match else None) or (slug_match.group(1).strip() if slug_match else None)
    last_step = None
    if last_step_line:
        step_match = re.search(r"action=([^\s]+)", last_step_line)
        if step_match:
            last_step = step_match.group(1).strip()
    return {
        "status": status,
        "tone": tone,
        "last_started": parse_ts(last_start),
        "last_finished": parse_ts(last_ok or last_fail),
        "last_line": last_line or last_warn,
        "last_result": last_result,
        "last_agent": last_agent,
        "last_step": last_step,
        "agents_touched": len(agent_hits),
        "should_auto": status != "running" and (not parse_ts(last_ok or last_fail) or (time.time() - (SELF_TRAIN_LOG.stat().st_mtime if SELF_TRAIN_LOG.exists() else 0)) > 21600),
        "log_path": str(SELF_TRAIN_LOG),
    }

def build_startup_proposals(
    services: dict[str, Any],
    agents: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    selected_project: str | None,
    training: dict[str, Any],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    down = [name for name, service in services.items() if not service.get("ok")]
    broken_agents = [agent for agent in agents if agent.get("last_error")]
    selected_item = next((item for item in projects if item["project"] == selected_project), None)
    if selected_item:
        proposals.append({
            "title": f"Pousser {selected_project}",
            "why": selected_item.get("hint"),
            "action": None,
            "panel": "watch",
            "project": selected_project,
            "tone": "selected",
        })
    if down:
        proposals.append({
            "title": f"Réparer {down[0]}",
            "why": "Un service central est dégradé. Le remettre en ligne redonne de la marge à tout le cockpit.",
            "action": "restart_stack" if len(down) > 1 else "repair_ollama",
            "panel": "services",
            "tone": "bad",
        })
    if broken_agents:
        proposals.append({
            "title": f"Débloquer {broken_agents[0]['name']}",
            "why": broken_agents[0].get("last_error") or broken_agents[0].get("task_current"),
            "action": "agent_pulse_now",
            "panel": "agents",
            "tone": "warn",
        })
    if training.get("should_auto"):
        proposals.append({
            "title": "Lancer l’auto-entraînement",
            "why": "Audit skills, selftest UI et passe evolver pour faire progresser IRIS sans coût supplémentaire.",
            "action": "self_train_cycle",
            "panel": "summary",
            "tone": "ok",
        })
    for project in projects:
        if project["project"] == selected_project:
            continue
        proposals.append({
            "title": f"Explorer {project['project']}",
            "why": project.get("hint"),
            "action": None,
            "panel": "watch",
            "project": project["project"],
            "tone": project.get("tone", "ok"),
        })
        if len(proposals) >= 5:
            break
    seen: set[str] = set()
    uniq = []
    for proposal in proposals:
        key = proposal["title"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(proposal)
    return uniq[:5]

def build_improvement_queue(
    services: dict[str, Any],
    agents: list[dict[str, Any]],
    watch: dict[str, Any],
    projects: list[dict[str, Any]],
    selected_project: str | None,
    training: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    down = [name for name, service in services.items() if not service.get("ok")]
    broken_agents = [agent for agent in agents if agent.get("last_error")]
    selected_item = next((item for item in projects if item["project"] == selected_project), None)

    if down:
        items.append({
            "title": f"Réparer {down[0]}",
            "why": "Le mesh n’est pas entièrement vert. Revenir à 100% rend toute l’autonomie plus fiable.",
            "action": "restart_stack" if len(down) > 1 else "repair_ollama",
            "panel": "services",
            "tone": "bad",
        })
    if broken_agents:
        items.append({
            "title": f"Débloquer {broken_agents[0]['name']}",
            "why": broken_agents[0].get("blocked_by") or broken_agents[0].get("task_current"),
            "action": "agent_pulse_now",
            "panel": "agents",
            "tone": "warn",
        })
    if training.get("should_auto"):
        items.append({
            "title": "Auto-train IRIS",
            "why": "Relancer l’audit des skills et la passe evolver pour améliorer le système sans coût supplémentaire.",
            "action": "self_train_cycle",
            "panel": "summary",
            "tone": "ok",
        })
    if not watch.get("current_site") and watch.get("watch_sites_count"):
        items.append({
            "title": "Redémarrer la veille",
            "why": "La queue watch existe mais aucun scan n’est en cours.",
            "action": "watch_now",
            "panel": "watch",
            "tone": "warn",
        })
    if selected_item:
        items.append({
            "title": f"Pousser {selected_project}",
            "why": selected_item.get("hint") or selected_item.get("summary"),
            "action": None,
            "project": selected_project,
            "panel": "summary",
            "tone": "selected",
        })
    for project in projects:
        if project["project"] == selected_project or not project.get("priority"):
            continue
        items.append({
            "title": f"Explorer {project['project']}",
            "why": project.get("hint"),
            "action": None,
            "project": project["project"],
            "panel": "summary",
            "tone": project.get("tone", "ok"),
        })
    uniq: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = item["title"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq[:5]

def build_launch_briefing(
    services: dict[str, Any],
    agents: list[dict[str, Any]],
    watch: dict[str, Any],
    projects: list[dict[str, Any]],
    selected_project: str | None,
    training: dict[str, Any],
    startup: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> dict[str, Any]:
    down = [name for name, service in services.items() if not service.get("ok")]
    broken_agents = [agent for agent in agents if agent.get("last_error")]
    recommended_project = selected_project or next((item["project"] for item in projects if item.get("priority")), None) or (projects[0]["project"] if projects else None)
    top_move = startup[0]["title"] if startup else (improvements[0]["title"] if improvements else "Continuer la boucle autonome")
    tone = "bad" if down or broken_agents else "warn" if training.get("should_auto") else "ok"
    headline = f"{recommended_project} en tête" if recommended_project else "IRIS prêt"
    operator_note = (
        f"Commence par {top_move.lower()}."
        if top_move
        else "Le système est stable. Tu peux choisir un projet ou laisser tourner la veille."
    )
    risk = down[0] if down else (broken_agents[0]["name"] if broken_agents else "aucun")
    lines = [
        f"Projet recommandé: {recommended_project or 'IRIS'}",
        f"Action immédiate: {top_move}",
        f"Risque principal: {risk}",
    ]
    if watch.get("current_site"):
        lines.append(f"Veille active sur {strip_protocol(watch['current_site'])}")
    elif watch.get("watch_sites_count"):
        lines.append(f"Veille prête sur {watch['watch_sites_count']} sites")
    if training.get("status") == "running":
        lines.append("Auto-train déjà en cours")
    elif training.get("should_auto"):
        lines.append("Une nouvelle passe d’auto-train est pertinente")
    return {
        "headline": headline,
        "operator_note": operator_note,
        "recommended_project": recommended_project,
        "next_move": top_move,
        "risk": risk,
        "tone": tone,
        "lines": lines[:4],
    }

def resolve_action_commands(action: str) -> list[list[str]]:
    if action in ("normal", "work", "light", "autopilot"):
        action = f"mode_{action}"
    if action == "watch_radar_note":
        return [[str(NATIVE / "bin" / "iris-watch-radar"), str(OBSIDIAN_VAULT)]]
    if action == "observe_agents":
        return [[str(NATIVE / "bin" / "iris-agent-observe"), str(OBSIDIAN_VAULT)]]
    if action in {"agent_pulse_now", "refresh"}:
        commands: list[list[str]] = []
        pulse_suite = [
            [str(NATIVE / "bin" / "iris-agent-observe"), str(OBSIDIAN_VAULT)],
            [str(NATIVE / "bin" / "iris-watch-radar"), str(OBSIDIAN_VAULT)],
            [str(AUTONOMY / "bin" / "iris-watchdog")],
            [str(AUTONOMY / "bin" / "iris-freshness-audit")],
        ]
        if action == "refresh":
            pulse_suite.append([str(NATIVE / "bin" / "iris-skill-sync")])
        for cmd in pulse_suite:
            if Path(cmd[0]).exists():
                commands.append(cmd)
        return commands
    return [[str(cmd)] for cmd in ACTION_MAP.get(action, []) if cmd.exists()]

def command_exists(path: Path) -> bool:
    return path.exists() and path.is_file()

def check_site_watch_runtime() -> dict[str, Any]:
    venv_python = NATIVE / "venv" / "bin" / "python"
    watch_script = NATIVE / "bin" / "iris-watch-sites-now"
    runtime = {
        "watch_script_exists": command_exists(watch_script),
        "venv_python_exists": command_exists(venv_python),
        "venv_python_path": str(venv_python),
        "requests_ready": False,
    }
    if command_exists(venv_python):
        try:
            proc = subprocess.run(
                [str(venv_python), "-c", "import requests; print(requests.__version__)"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            runtime["requests_ready"] = proc.returncode == 0
            runtime["requests_version"] = proc.stdout.strip() or None
            runtime["requests_error"] = proc.stderr.strip() or None
        except Exception as e:
            runtime["requests_error"] = str(e)
    return runtime

def read_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                merged = dict(default)
                merged.update(loaded)
                return merged
    except Exception:
        pass
    return dict(default)

def first_existing_path(candidates: list[Path]) -> Path | None:
    return next((candidate for candidate in candidates if candidate.exists()), None)

def resolve_whisper_runtime() -> dict[str, Any]:
    root = first_existing_path(WHISPER_ROOT_CANDIDATES)
    cli = None
    model = None
    if root:
        cli = first_existing_path(
            [
                root / "build" / "bin" / "whisper-cli",
                root / "build" / "bin" / "Release" / "whisper-cli",
            ]
        )
        model = first_existing_path(
            [
                root / "models" / "ggml-base.bin",
                root / "models" / "ggml-small.bin",
                root / "models" / "ggml-base.en.bin",
            ]
        )
    multilingual = bool(model and model.name.endswith(".bin") and not model.name.endswith(".en.bin"))
    return {
        "root": root,
        "cli": cli,
        "model": model,
        "stt_available": bool(cli and model),
        "multilingual": multilingual,
    }

def resolve_piper_runtime() -> dict[str, Any]:
    model = first_existing_path(PIPER_VOICE_CANDIDATES)
    config = first_existing_path(PIPER_CONFIG_CANDIDATES)
    python_bin = PIPER_VENV_PYTHON if PIPER_VENV_PYTHON.exists() else None
    return {
        "python_bin": python_bin,
        "model": model,
        "config": config,
        "tts_available": bool(python_bin and model and config and AFPLAY_BIN.exists()),
    }

def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False

def write_voice_state(status: str, detail: str, *, pid: int | None = None, last_text: str | None = None) -> dict[str, Any]:
    payload = {
        "status": status,
        "detail": detail,
        "pid": pid,
        "last_text": last_text,
        "updated": iso_now(),
        "tts_available": SAY_BIN.exists(),
        "native_voice": True,
    }
    VOICE_STATE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload

def refresh_voice_state() -> dict[str, Any]:
    global VOICE_PROCESS
    state = read_json_file(
        VOICE_STATE_FILE,
        {
            "status": "idle",
            "detail": "Voix femme locale prête",
            "pid": None,
            "last_text": None,
            "updated": None,
            "tts_available": SAY_BIN.exists(),
            "native_voice": True,
        },
    )
    pid = state.get("pid")
    active = False
    if VOICE_PROCESS and VOICE_PROCESS.poll() is None:
        pid = VOICE_PROCESS.pid
        active = True
    elif process_alive(pid if isinstance(pid, int) else None):
        active = True
    if state.get("status") == "speaking" and not active:
        state = write_voice_state("idle", "Voix femme locale prête", last_text=state.get("last_text"))
    return state

def stop_local_voice() -> dict[str, Any]:
    global VOICE_PROCESS
    stopped = False
    current = refresh_voice_state()
    pid = current.get("pid")
    if VOICE_PROCESS and VOICE_PROCESS.poll() is None:
        try:
            VOICE_PROCESS.terminate()
            stopped = True
        except Exception:
            pass
    if not stopped and isinstance(pid, int) and process_alive(pid):
        try:
            os.kill(pid, 15)
            stopped = True
        except Exception:
            pass
    VOICE_PROCESS = None
    detail = "Voix femme locale prête"
    return {"ok": True, "stopped": stopped, "state": write_voice_state("idle", detail, last_text=current.get("last_text"))}

def speak_local_voice(text: str, voice: str | None = None) -> dict[str, Any]:
    global VOICE_PROCESS
    content = re.sub(r"\s+", " ", text or "").strip()
    if not content:
        return {"ok": False, "stderr": "texte vide"}
    stop_local_voice()
    piper_runtime = resolve_piper_runtime()
    if piper_runtime.get("tts_available"):
        shell_script = f"""
TMP_FILE=$(mktemp "{VOICE_INPUT_DIR}/piper-XXXXXX.wav")
cleanup() {{
  rm -f "$TMP_FILE"
}}
trap cleanup EXIT
printf "%s" "$IRIS_PIPER_TEXT" | "$IRIS_PIPER_PYTHON" -m piper -m "$IRIS_PIPER_MODEL" -c "$IRIS_PIPER_CONFIG" -f "$TMP_FILE" >> "{PIPER_LOG_FILE}" 2>&1
status=$?
if [ "$status" -eq 0 ]; then
  "{AFPLAY_BIN}" "$TMP_FILE" >> "{PIPER_LOG_FILE}" 2>&1
  status=$?
fi
exit "$status"
"""
        env = dict(os.environ)
        env.update(
            {
                "IRIS_PIPER_TEXT": content[:900],
                "IRIS_PIPER_PYTHON": str(piper_runtime["python_bin"]),
                "IRIS_PIPER_MODEL": str(piper_runtime["model"]),
                "IRIS_PIPER_CONFIG": str(piper_runtime["config"]),
            }
        )
        try:
            proc = subprocess.Popen(
                ["/bin/zsh", "-lc", shell_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
            )
            VOICE_PROCESS = proc
            state = write_voice_state("speaking", "Voix femme Piper en cours", pid=proc.pid, last_text=content[:900])
            return {"ok": True, "engine": "piper", "pid": proc.pid, "state": state}
        except Exception as e:
            pass
    if not SAY_BIN.exists():
        return {"ok": False, "stderr": "commande say absente"}
    cmd = [str(SAY_BIN)]
    voice = voice or DEFAULT_SAY_VOICE
    if voice:
        cmd.extend(["-v", voice])
    cmd.append(content[:900])
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        VOICE_PROCESS = proc
        state = write_voice_state("speaking", "Voix femme locale en cours", pid=proc.pid, last_text=content[:900])
        return {"ok": True, "engine": "say", "command": cmd, "pid": proc.pid, "state": state}
    except Exception as e:
        return {"ok": False, "command": cmd, "stderr": str(e)}

def transcribe_local_audio(audio_bytes: bytes, language: str | None = None) -> dict[str, Any]:
    runtime = resolve_whisper_runtime()
    cli = runtime.get("cli")
    model = runtime.get("model")
    if not runtime.get("stt_available") or not cli or not model:
        return {
            "ok": False,
            "speech_detected": False,
            "detail": "whisper.cpp indisponible",
            "runtime": {
                "stt_available": False,
                "whisper_cli_path": str(cli) if cli else None,
                "whisper_model_path": str(model) if model else None,
            },
        }
    payload = audio_bytes or b""
    if not payload:
        return {"ok": False, "speech_detected": False, "detail": "audio vide"}
    chosen_language = (language or "auto").strip() or "auto"
    audio_path: Path | None = None
    txt_path: Path | None = None
    out_root: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(VOICE_INPUT_DIR), prefix="voice-", suffix=".wav", delete=False) as handle:
            handle.write(payload)
            audio_path = Path(handle.name)
        out_root = audio_path.with_suffix("")
        txt_path = out_root.with_suffix(".txt")
        cmd = [
            str(cli),
            "-m",
            str(model),
            "-f",
            str(audio_path),
            "-l",
            chosen_language,
            "-t",
            "4",
            "-otxt",
            "-of",
            str(out_root),
            "-np",
            "-nt",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
        )
        transcript = ""
        if txt_path.exists():
            transcript = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not transcript:
            transcript = (proc.stdout or "").strip()
        transcript = re.sub(r"\s+", " ", transcript).strip()
        speech_detected = bool(transcript)
        detail = "Transcription locale prête" if speech_detected else "Aucune parole détectée"
        return {
            "ok": proc.returncode == 0,
            "speech_detected": speech_detected,
            "text": transcript,
            "detail": detail,
            "language": chosen_language,
            "command": cmd,
            "stderr": (proc.stderr or "").strip() or None,
            "runtime": {
                "stt_available": True,
                "whisper_cli_path": str(cli),
                "whisper_model_path": str(model),
                "multilingual": runtime.get("multilingual"),
            },
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "speech_detected": False, "detail": "Transcription locale expirée"}
    except Exception as e:
        return {"ok": False, "speech_detected": False, "detail": f"Transcription locale impossible: {e}"}
    finally:
        for candidate in [txt_path, audio_path]:
            try:
                if candidate and candidate.exists():
                    candidate.unlink()
            except Exception:
                pass

def build_voice_runtime() -> dict[str, Any]:
    state = refresh_voice_state()
    whisper_runtime = resolve_whisper_runtime()
    piper_runtime = resolve_piper_runtime()
    stt_available = bool(whisper_runtime.get("stt_available"))
    cli = whisper_runtime.get("cli")
    model = whisper_runtime.get("model")
    piper_python = piper_runtime.get("python_bin")
    piper_model = piper_runtime.get("model")
    piper_config = piper_runtime.get("config")
    piper_available = bool(piper_runtime.get("tts_available"))
    return {
        **state,
        "say_bin_exists": SAY_BIN.exists(),
        "say_bin_path": str(SAY_BIN),
        "default_say_voice": DEFAULT_SAY_VOICE,
        "piper_available": piper_available,
        "piper_python_path": str(piper_python) if piper_python else None,
        "piper_model_path": str(piper_model) if piper_model else None,
        "piper_config_path": str(piper_config) if piper_config else None,
        "voice_persona": "femme-fr" if piper_available or SAY_BIN.exists() else None,
        "stt_available": stt_available,
        "whisper_cli_path": str(cli) if cli else None,
        "whisper_model_path": str(model) if model else None,
        "whisper_multilingual": whisper_runtime.get("multilingual", False),
        "speech_input_mode": "whisper.cpp-local" if stt_available else "browser-native-shell",
        "speech_output_mode": "piper-local" if piper_available else "macos-say",
    }

def check_qdrant_runtime() -> dict[str, Any]:
    out: dict[str, Any] = {
        "base_url": SERVICE_URLS["Qdrant"],
        "collection": "iris_obsidian",
        "ok": False,
        "exists": False,
        "points_count": 0,
        "indexed_vectors_count": 0,
    }
    try:
        r = requests.get(f"{SERVICE_URLS['Qdrant']}/collections/iris_obsidian", timeout=4)
        out["status"] = r.status_code
        if r.ok:
            payload = r.json().get("result", {})
            details = payload.get("config", {})
            meta = payload.get("points_count")
            out["ok"] = True
            out["exists"] = True
            out["details"] = details
            out["points_count"] = payload.get("points_count", 0)
            out["indexed_vectors_count"] = payload.get("indexed_vectors_count", 0)
            out["segments_count"] = payload.get("segments_count", 0)
            out["status_text"] = payload.get("status")
            out["vector_size"] = (((details.get("params") or {}).get("vectors") or {}).get("size"))
        elif r.status_code == 404:
            out["exists"] = False
    except Exception as e:
        out["error"] = str(e)
    return out

def check_searx_json() -> dict[str, Any]:
    out: dict[str, Any] = {
        "base_url": SERVICE_URLS["SearXNG"],
        "ok": False,
    }
    try:
        r = requests.get(
            f"{SERVICE_URLS['SearXNG']}/search",
            params={"q": "iris local ai", "format": "json", "language": "fr", "safesearch": 0},
            timeout=8,
        )
        out["status"] = r.status_code
        out["content_type"] = r.headers.get("content-type")
        if r.ok and "json" in (r.headers.get("content-type") or "").lower():
            data = r.json()
            results = data.get("results", [])
            out["ok"] = True
            out["results_count"] = len(results)
        else:
            out["body_excerpt"] = r.text[:180]
    except Exception as e:
        out["error"] = str(e)
    return out

def build_bridge_state() -> dict[str, Any]:
    launcher = BASE / "bin" / "iris-v11-open-native-app"
    return {
        "mode": "native-installed" if APP_BUNDLE.exists() else ("native-ready" if launcher.exists() else "web-only"),
        "shell_launcher_exists": launcher.exists(),
        "shell_launcher_path": str(launcher),
        "installed_app_exists": APP_BUNDLE.exists(),
        "installed_app_path": str(APP_BUNDLE),
        "canonical_open_command": ["open", str(APP_BUNDLE)] if APP_BUNDLE.exists() else None,
        "core_config_endpoint": "/api/core-config",
        "ready_endpoint": "/api/ready",
        "state_endpoint": "/api/state",
        "watch_endpoint": "/api/watch",
        "services_endpoint": "/api/services",
        "diagnostics_endpoint": "/api/diagnostics",
        "action_endpoint": "/api/action/{action}",
        "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

def build_diagnostics(service_health: dict[str, Any] | None = None) -> dict[str, Any]:
    launcher_log_lines = tail(NATIVE_LAUNCHER_LOG, 80)
    launcher_meta = parse_line_meta(launcher_log_lines)
    site_watch_runtime = check_site_watch_runtime()
    qdrant_runtime = check_qdrant_runtime()
    searx_json = check_searx_json()
    voice_runtime = build_voice_runtime()
    return {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "app_bundle_exists": APP_BUNDLE.exists(),
        "app_bundle_path": str(APP_BUNDLE),
        "launcher_exists": (BASE / "bin" / "iris-v11-open-native-app").exists(),
        "launcher_log_path": str(NATIVE_LAUNCHER_LOG),
        "launcher_log_exists": NATIVE_LAUNCHER_LOG.exists(),
        "launcher_last_line": launcher_meta.get("last"),
        "launcher_last_error": launcher_meta.get("error"),
        "ready_endpoint": "/api/ready",
        "obsidian_vault_exists": OBSIDIAN_VAULT.exists(),
        "obsidian_vault_path": str(OBSIDIAN_VAULT),
        "canonical_vault_path": str(CANONICAL_VAULT),
        "legacy_vault_paths": [str(path) for path in LEGACY_VAULTS],
        "site_watch_runtime": site_watch_runtime,
        "qdrant_runtime": qdrant_runtime,
        "searxng_json_runtime": searx_json,
        "voice_runtime": voice_runtime,
        "recovery_actions": [
            "watch_now",
            "agent_pulse_now",
            "observe_agents",
            "watch_radar_note",
            "repair_ollama",
            "prepare_qdrant",
            "reindex_memory",
            "self_train_cycle",
            "restart_stack",
            "audit_skills",
        ],
        "service_health": service_health if service_health is not None else build_services(),
    }

def build_agents() -> list[dict[str, Any]]:
    out = []
    for name, slug, paths in AGENTS:
        identity = agent_identity(slug, name)
        p = latest_existing(paths)
        lines = tail(p, 220)
        meta = parse_line_meta(lines)
        state = "travaille" if meta["success"] else "attente"
        task = TASK_BY_SLUG.get(slug)
        nxt = NEXT_BY_SLUG.get(slug)
        why = WHY_BY_SLUG.get(slug, task or "tenir la boucle autonome à jour")
        where = p.name if p else "aucun log"
        tone = "ok"
        progress = 28
        if slug == "site_watch":
            current, next_url = extract_current_watch(lines)
            if current:
                task = f"scan séquentiel des sites de veille ({current})"
                where = current
                progress = 76
            if next_url:
                nxt = f"scanner ensuite {next_url}"
        if slug == "agent_observe" and meta["success"] and not re.search(r"_ok", meta["success"], re.I):
            meta["success"] = "AGENT_OBSERVE_OK"
        if meta["error"]:
            state = "bloqué"
            tone = "bad"
            progress = 16
        elif meta["success"]:
            progress = 82 if slug != "watchdog" else 96
            tone = "warn" if slug in {"site_watch", "research_light", "research_deep"} else "ok"
        elif slug in {"incubator", "system_evolver", "chief_supervisor"}:
            progress = 44
            tone = "warn"
        last_seen = parse_ts(meta["last"] or meta["success"] or meta["error"])
        confidence_pct = 34 if tone == "bad" else 58 if tone == "warn" else 86
        training_recipe = TRAINING_PLAN_BY_SLUG.get(slug, {})
        out.append({
            "name": identity["display_name"],
            "codename": identity["codename"],
            "role_title": identity["role"],
            "slug": slug,
            "state": state,
            "tone": tone,
            "model_used": MODEL_BY_SLUG.get(slug),
            "task_current": task,
            "why_it_matters": why,
            "where_it_works": where,
            "progress_label": meta["error"] or meta["success"] or task,
            "progress_pct": progress,
            "confidence_pct": confidence_pct,
            "autonomy_grade": autonomy_grade(progress, tone, state),
            "last_seen": last_seen,
            "blocked_by": meta["error"],
            "operator_line": build_operator_line(task, why, where, state, meta["error"]),
            "learning_loop": LEARNING_BY_SLUG.get(slug),
            "output_surface": OUTPUT_BY_SLUG.get(slug),
            "training_objective": training_recipe.get("objective"),
            "training_actions": training_recipe.get("actions", []),
            "next_planned_action": nxt,
            "last_success": meta["success"],
            "last_error": meta["error"],
            "log_path": str(p) if p else None,
        })
    return out

def find_mode_power() -> tuple[str, str]:
    candidates = [
        NATIVE / "state" / "state.json",
        NATIVE / "state" / "mode.json",
        PREMIUM / "state" / "mode.json",
    ]
    existing = [p for p in candidates if p.exists()]
    existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for p in existing:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return str(d.get("power") or "ON"), str(d.get("mode") or "autopilot")
        except Exception:
            pass
    return "ON", "autopilot"

def build_watch(agents: list[dict[str, Any]]) -> dict[str, Any]:
    sites = read_watchlist()
    current = None
    next_site = None
    site_watch = next((a for a in agents if a["slug"] == "site_watch"), None)
    if site_watch and site_watch.get("last_success"):
        current, next_site = extract_current_watch([site_watch["last_success"]])
    preview = []
    for x in [current, next_site]:
        if x and x not in preview:
            preview.append(x)
    for s in sites:
        if s not in preview:
            preview.append(s)
        if len(preview) >= 6:
            break
    return {
        "watch_sites_count": len(sites),
        "current_site": current,
        "next_site": next_site,
        "preview": preview,
    }

def build_summary(
    services: dict[str, Any] | None = None,
    agents: list[dict[str, Any]] | None = None,
    watch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    services = services if services is not None else build_services()
    agents = agents if agents is not None else build_agents()
    watch = watch if watch is not None else build_watch(agents)
    power, mode = find_mode_power()
    chief_focus = infer_focus_from_chief(tail(latest_existing([AUTONOMY / "logs" / "chief.log"]), 60))
    incubator_raw = infer_incubator(tail(latest_existing([AUTONOMY / "logs" / "incubator.log"]), 60))
    projects, selected_project, priority_project = build_projects()
    incubator = incubator_focus(selected_project, projects, incubator_raw)
    training = parse_training_log()
    training_queue = build_training_plan(agents, selected_project)
    training_styles = build_training_styles(selected_project)
    utility_agents = build_utility_agents(selected_project)
    waiting = [a["name"] for a in agents if a["state"] != "travaille"]
    errors = [a["name"] for a in agents if a["last_error"]]
    next_actions = []
    if errors:
        next_actions.append(f"corriger le blocage de {errors[0]}")
    if waiting:
        next_actions.append(f"réactiver {waiting[0]}")
    if watch["current_site"]:
        next_actions.append(f"laisser finir le scan de {watch['current_site']}")
    if selected_project:
        next_actions.append(f"pousser un jalon concret sur {selected_project}")
    if not next_actions:
        next_actions.append("aucun blocage critique")
    startup = build_startup_proposals(services, agents, projects, selected_project, training)
    improvements = build_improvement_queue(services, agents, watch, projects, selected_project, training)
    briefing = build_launch_briefing(services, agents, watch, projects, selected_project, training, startup, improvements)
    return {
        "updated": iso_now(),
        "power": power,
        "mode": mode,
        "services_ok": sum(1 for v in services.values() if v["ok"]),
        "services_total": len(services),
        "services_down": [k for k, v in services.items() if not v["ok"]],
        "agents_working": [a["name"] for a in agents if a["state"] == "travaille"],
        "agents_waiting": waiting,
        "watch_sites": watch["watch_sites_count"],
        "watch_current": watch["current_site"],
        "next_actions": next_actions,
        "incubator": incubator,
        "projects": projects,
        "selected_project": selected_project,
        "priority_project": priority_project,
        "startup_proposals": startup,
        "improvement_queue": improvements,
        "launch_briefing": briefing,
        "training": training,
        "training_queue": training_queue,
        "training_styles": training_styles,
        "utility_agents": utility_agents,
        "chief_focus": chief_focus,
        "agent_states": {a["name"]: a["state"] for a in agents},
    }

def build_state() -> dict[str, Any]:
    services = build_services()
    agents = build_agents()
    watch = build_watch(agents)
    summary = build_summary(services=services, agents=agents, watch=watch)
    bridge = build_bridge_state()
    diagnostics = build_diagnostics(service_health=services)
    return {
        **summary,
        "summary": summary,
        "services": services,
        "service_health": services,
        "agents": agents,
        "watch": watch,
        "watch_radar": watch,
        "watch_queue": watch,
        "incubator": summary["incubator"],
        "incubator_proposals": summary["incubator"],
        "projects": summary["projects"],
        "selected_project": summary["selected_project"],
        "priority_project": summary["priority_project"],
        "startup_proposals": summary["startup_proposals"],
        "improvement_queue": summary["improvement_queue"],
        "launch_briefing": summary["launch_briefing"],
        "training": summary["training"],
        "training_queue": summary["training_queue"],
        "training_styles": summary["training_styles"],
        "utility_agents": summary["utility_agents"],
        "chief_focus": summary["chief_focus"],
        "timeline": build_timeline(agents),
        "models": build_models(),
        "mission_control": summary,
        "bridge": bridge,
        "bridge_state": bridge,
        "diagnostics": diagnostics,
    }

def build_ready_state() -> dict[str, Any]:
    config = read_core_config()
    agents = build_agents()
    watch = build_watch(agents)
    power, mode = find_mode_power()
    projects, selected_project, _priority = build_projects()
    qdrant_runtime = check_qdrant_runtime()
    voice_runtime = build_voice_runtime()
    summary = {
        "power": power,
        "mode": mode,
        "agent_count": len(agents),
        "watch_sites": watch["watch_sites_count"],
        "active_core": config.get("active", "sphere"),
        "selected_project": selected_project,
        "projects_count": len(projects),
        "memory_indexed": qdrant_runtime.get("points_count", 0),
        "voice_status": voice_runtime.get("status"),
    }
    ready = UI.exists() and bool(config.get("cores")) and isinstance(agents, list)
    return {
        "ready": ready,
        "updated": iso_now(),
        "ui_exists": UI.exists(),
        "app_bundle_exists": APP_BUNDLE.exists(),
        "active_core": config.get("active", "sphere"),
        "selected_project": selected_project,
        "summary": summary,
        "bridge": build_bridge_state(),
        "voice": voice_runtime,
    }

def build_timeline(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for a in agents:
        for key in ("last_success", "last_error"):
            line = a.get(key)
            if not line or line in seen:
                continue
            seen.add(line)
            rows.append({
                "slug": a["slug"],
                "name": a["name"],
                "kind": "error" if key == "last_error" else "ok",
                "ts": parse_ts(line),
                "text": line,
            })
    rows.sort(key=lambda x: x["ts"], reverse=True)
    return rows[:16]

def parse_ts(line: str | None) -> str:
    if not line:
        return ""
    m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
    return m.group(1) if m else ""

def spawn_self_train_cycle() -> dict[str, Any]:
    training = parse_training_log()
    if training.get("status") == "running":
        return {"ok": True, "already_running": True, "log_path": str(SELF_TRAIN_LOG)}
    selected_project = read_operator_state().get("selected_project") or "none"
    agents = build_agents()
    training_queue = build_training_plan(agents, selected_project)
    available_steps = [item for item in training_queue if item.get("commands")]
    if not available_steps:
        return {"ok": False, "stderr": "aucune brique d’auto-entraînement disponible"}
    log_q = shlex.quote(str(SELF_TRAIN_LOG))
    project_q = shlex.quote(str(selected_project))
    block = [
        "warn_count=0",
        "executed_actions=''",
        f'echo "$(date \'+%Y-%m-%dT%H:%M:%S\') SELF_TRAIN_START project={project_q} agents={len(available_steps)}"',
    ]
    for item in available_steps:
        slug_q = shlex.quote(str(item["slug"]))
        name_q = shlex.quote(str(item["name"]))
        objective_q = shlex.quote(str(item["objective"]))
        eligible_q = "1" if item.get("eligible") else "0"
        block.append(
            f'echo "$(date \'+%Y-%m-%dT%H:%M:%S\') SELF_TRAIN_AGENT slug={slug_q} name={name_q} objective={objective_q} eligible={eligible_q}"'
        )
        for step in item["commands"]:
            action = str(step["action"])
            action_q = shlex.quote(action)
            cmd = " ".join(shlex.quote(str(part)) for part in step["command"])
            block.append(f'case " $executed_actions " in *" {action} "*) already_done=1 ;; *) already_done=0 ;; esac')
            block.append(
                f'if [ "$already_done" -eq 1 ]; then '
                f'echo "$(date \'+%Y-%m-%dT%H:%M:%S\') SELF_TRAIN_REUSE action={action_q} slug={slug_q}"; '
                f'else '
                f'echo "$(date \'+%Y-%m-%dT%H:%M:%S\') SELF_TRAIN_STEP action={action_q} slug={slug_q}"; '
                f'{cmd} || {{ warn_count=$((warn_count+1)); echo "$(date \'+%Y-%m-%dT%H:%M:%S\') SELF_TRAIN_WARN action={action_q} slug={slug_q} project={project_q}"; }}; '
                f'executed_actions="$executed_actions {action}"; '
                f'fi'
            )
        block.append(f'echo "$(date \'+%Y-%m-%dT%H:%M:%S\') SELF_TRAIN_AGENT_OK slug={slug_q}"')
    block.append(f'echo "$(date \'+%Y-%m-%dT%H:%M:%S\') SELF_TRAIN_OK project={project_q} warnings=$warn_count agents={len(available_steps)}"')
    script = "{ " + "; ".join(block) + f"; }} >> {log_q} 2>&1"
    try:
        subprocess.Popen(
            ["bash", "-lc", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {
            "ok": True,
            "spawned": True,
            "selected_project": selected_project,
            "steps": [item["slug"] for item in available_steps],
            "agents": [item["name"] for item in available_steps],
            "log_path": str(SELF_TRAIN_LOG),
        }
    except Exception as e:
        return {"ok": False, "stderr": str(e), "log_path": str(SELF_TRAIN_LOG)}

def select_project(project: str) -> dict[str, Any]:
    projects, _selected, _priority = build_projects()
    names = {item["project"] for item in projects}
    if project not in names:
        return {"ok": False, "error": "projet inconnu", "projects": projects}
    state = write_operator_state({"selected_project": project})
    return {"ok": True, "selected_project": state["selected_project"], "projects": build_projects()[0]}

def run_action(action: str) -> dict[str, Any]:
    if action in UTILITY_APP_ACTIONS:
        return open_application(UTILITY_APP_ACTIONS[action])
    if action == "open_native_shell":
        return open_native_app()
    if action == "self_train_cycle":
        return spawn_self_train_cycle()
    if action in {"incubator_now", "chief_now", "evolver_now", "skill_sync", "ui_selftest", "agent_pulse_now", "refresh", "reindex_memory"}:
        return spawn_action(action)
    if action == "observe_agents":
        return launch_terminal_command(TERMINAL_OBSERVE)
    if action == "watch_radar_note":
        return launch_terminal_command(TERMINAL_WATCH_RADAR)
    commands = resolve_action_commands(action)
    for cmd in commands:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {"ok": proc.returncode == 0, "command": cmd, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
        except Exception as e:
            return {"ok": False, "command": cmd, "stderr": str(e)}
    return {"ok": False, "stderr": "commande introuvable"}

def spawn_action(action: str) -> dict[str, Any]:
    if action in UTILITY_APP_ACTIONS:
        return open_application(UTILITY_APP_ACTIONS[action])
    if action == "open_native_shell":
        return open_native_app()
    if action == "self_train_cycle":
        return spawn_self_train_cycle()
    commands = resolve_action_commands(action)
    for cmd in commands:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {"ok": True, "command": cmd, "spawned": True}
        except Exception as e:
            return {"ok": False, "command": cmd, "stderr": str(e)}
    return {"ok": False, "stderr": "commande introuvable"}

def spawn_url_in_browser(url: str) -> dict[str, Any]:
    if not re.match(r"^https?://", url or "", re.I):
        return {"ok": False, "stderr": "url invalide"}
    try:
        cmd = ["open", url]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "command": cmd}
    except Exception as e:
        return {"ok": False, "stderr": str(e)}

def open_native_app() -> dict[str, Any]:
    if not APP_BUNDLE.exists():
        return {"ok": False, "stderr": f"app absente: {APP_BUNDLE}"}
    cmd = ["open", "-a", str(APP_BUNDLE)]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "command": cmd, "spawned": True}
    except Exception as e:
        return {"ok": False, "command": cmd, "stderr": str(e)}

def spawn_companion_restart() -> dict[str, Any]:
    plist = HOME / "Library" / "LaunchAgents" / "com.iris.v3.companion.plist"
    if not plist.exists():
        return {"ok": False, "stderr": f"LaunchAgent introuvable: {plist}"}
    uid = os.getuid()
    label = f"gui/{uid}/com.iris.v3.companion"
    cmd = ["launchctl", "kickstart", "-k", label]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "command": cmd, "spawned": True}
    except Exception as e:
        return {"ok": False, "command": cmd, "stderr": str(e)}

def open_path(path: Path) -> dict[str, Any]:
    try:
        subprocess.Popen(
            ["open", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "command": ["open", str(path)]}
    except Exception as e:
        return {"ok": False, "stderr": str(e)}

def open_application(app_name: str) -> dict[str, Any]:
    try:
        cmd = ["open", "-a", app_name]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "command": cmd}
    except Exception as e:
        return {"ok": False, "stderr": str(e), "command": ["open", "-a", app_name]}

def launch_terminal_command(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "stderr": "commande Terminal introuvable", "command": str(path)}
    try:
        subprocess.Popen(
            ["open", "-a", "Terminal", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "command": ["open", "-a", "Terminal", str(path)], "spawned": True}
    except Exception as e:
        return {"ok": False, "command": ["open", "-a", "Terminal", str(path)], "stderr": str(e)}

def choose_chat_model() -> str | None:
    models = build_models().get("available", [])
    pref = ["qwen3:4b", "qwen3:8b", "qwen3.5:9b", "gpt-oss:20b", "qwen2.5-coder:7b"]
    for want in pref:
        if want in models:
            return want
    return models[0] if models else None

def quick_summary() -> str:
    s = build_summary()
    parts = [
        f"Je suis en mode {s['mode']}.",
        f"{s['services_ok']}/{s['services_total']} services sont en ligne.",
        f"{len(s['agents_working'])} agents travaillent.",
    ]
    if s.get("selected_project"):
        parts.append(f"Projet incubator sélectionné: {s['selected_project']}.")
    if s.get("watch_current"):
        parts.append(f"Je surveille actuellement {s['watch_current']}.")
    return " ".join(parts)

def rotating_choice(options: list[str]) -> str:
    if not options:
        return ""
    return options[int(time.time() // 7) % len(options)]

def contextual_smalltalk(message: str) -> str | None:
    lower = message.lower().strip()
    s = build_summary()
    project = s.get("selected_project") or "IRIS"
    services_ok = s.get("services_ok", 0)
    services_total = s.get("services_total", 0)
    agents = len(s.get("agents_working", []))
    next_move = (s.get("next_actions") or ["continuer la boucle autonome"])[0]

    if any(x in lower for x in ["comment ça va", "comment ca va", "ça va", "ca va", "tu vas bien"]):
        return rotating_choice([
            f"Je vais bien. {services_ok}/{services_total} services sont verts et je garde {project} dans ma ligne de mire.",
            f"Je suis stable et bien réveillée. {agents} agents tournent et mon prochain bon mouvement, c’est {next_move}.",
            f"Plutôt bien. Le mesh tient, {project} reste prioritaire, et je suis prête à pousser une vraie action utile.",
        ])
    if lower in {"salut", "bonjour", "hello", "yo", "hey", "coucou"}:
        return rotating_choice([
            f"Salut. Je suis là, stable, et {project} reste le sujet le plus chaud.",
            f"Bonjour. Le système tient bien, et je peux te briefer, agir ou te laisser piloter.",
            f"Salut. Je suis prête, avec {agents} agents actifs et un prochain mouvement déjà identifié.",
        ])
    if any(x in lower for x in ["merci", "thank you", "thanks"]):
        return rotating_choice([
            "Avec plaisir. Je reste là si tu veux pousser le prochain jalon.",
            "Toujours. On peut enchaîner direct sur l’action suivante.",
            "Avec joie. Donne-moi juste l’impulsion suivante.",
        ])
    return None

def match_intent(haystack: str, needle: str) -> bool:
    if " " in needle:
        return needle in haystack
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack, re.I) is not None

def handle_direct_command(message: str) -> dict[str, Any] | None:
    lower = message.lower()
    smalltalk = contextual_smalltalk(message)
    if smalltalk:
        return {"reply": smalltalk, "summary": build_summary()}
    mapping = [
        (["autopilot", "auto pilote"], "mode_autopilot", "Je passe en autopilot."),
        (["travail", "work mode", "mode travail"], "mode_work", "Je passe en mode travail."),
        (["veille légère", "mode veille", "light mode"], "mode_light", "Je passe en veille légère."),
        (["mode normal", "normal mode"], "mode_normal", "Je passe en mode normal."),
        (["éteins", "eteins", "power off", "arrête iris", "arrete iris"], "power_off", "Je coupe le système."),
        (["allume", "power on", "démarre", "demarre"], "power_on", "Je rallume le système."),
        (["veille maintenant", "scan maintenant", "watch now"], "watch_now", "Je lance une veille immédiate."),
        (["pulse", "rafraîchis les agents", "refresh agents"], "agent_pulse_now", "Je relance la pulse des agents."),
        (["relance tout", "restart stack", "restart iris", "redémarre la stack"], "restart_stack", "Je relance la stack locale."),
        (["répare ollama", "repare ollama", "fix ollama"], "repair_ollama", "Je tente une réparation d’Ollama."),
        (["prépare qdrant", "prepare qdrant"], "prepare_qdrant", "Je prépare Qdrant pour les embeddings."),
        (["audit skills", "audit des skills", "audit skills iris"], "audit_skills", "Je lance un audit des skills."),
        (["auto train", "self train", "entraine toi", "entraîne toi", "auto apprentissage"], "self_train_cycle", "Je lance un cycle d’auto-entraînement local."),
        (["sync skills", "skill sync"], "skill_sync", "Je resynchronise les skills locaux."),
        (["observe agents", "observe les agents", "agent observe"], "observe_agents", "Je force une observation des agents."),
        (["watch radar note", "génère watch radar", "genere watch radar"], "watch_radar_note", "Je régénère la note Watch Radar."),
        (["ouvre obsidian"], "open_obsidian", "J’ouvre Obsidian."),
        (["ouvre webui", "ouvre open webui"], "open_webui", "J’ouvre Open WebUI."),
        (["ouvre n8n"], "open_n8n", "J’ouvre n8n."),
        (["ouvre finder"], "open_finder", "J’ouvre Finder."),
        (["ouvre musique", "ouvre music"], "open_music", "J’ouvre Musique."),
        (["ouvre tv", "ouvre apple tv"], "open_tv", "J’ouvre TV."),
        (["ouvre quicktime", "ouvre quicktime player"], "open_quicktime", "J’ouvre QuickTime."),
        (["ouvre notes"], "open_notes", "J’ouvre Notes."),
        (["ouvre calendrier", "ouvre calendar"], "open_calendar", "J’ouvre Calendrier."),
        (["ouvre réglages", "ouvre reglages", "ouvre settings"], "open_settings", "J’ouvre les Réglages système."),
    ]
    for needles, action, reply in mapping:
        if any(match_intent(lower, n) for n in needles):
            result = run_action(action)
            s = build_summary()
            return {"reply": reply, "action": action, "result": result, "summary": s}
    if any(x in lower for x in ["statut", "status", "que fais tu", "tu fais quoi", "resume", "résume"]):
        return {"reply": quick_summary(), "summary": build_summary()}
    if any(x in lower for x in ["quel agent", "qui travaille", "qui fait quoi", "quels agents"]):
        agents = build_agents()
        if any(x in lower for x in ["veille", "watch", "scan"]):
            picks = [a for a in agents if a["slug"] in {"site_watch", "research_light", "research_deep"}]
        else:
            picks = [a for a in agents if a["state"] == "travaille"][:4]
        if not picks:
            return {"reply": "Aucun agent utile n’est remonté pour le moment.", "summary": build_summary()}
        chunks = [f"{agent['name']}: {agent.get('task_current') or 'aucune tâche claire'}" for agent in picks[:3]]
        return {"reply": " · ".join(chunks), "summary": build_summary()}
    if any(x in lower for x in ["diagnostic", "diagnostics", "santé système", "sante systeme"]):
        diag = build_diagnostics()
        reply = (
            f"Bundle app: {'ok' if diag['app_bundle_exists'] else 'absent'}. "
            f"Launcher log: {'ok' if diag['launcher_log_exists'] else 'absent'}. "
            f"Site Watch venv: {'ok' if diag['site_watch_runtime'].get('requests_ready') else 'à corriger'}."
        )
        return {"reply": reply, "summary": build_summary(), "diagnostics": diag}
    if any(x in lower for x in ["ouvre les logs", "open logs", "logs iris", "launcher log"]):
        result = open_path(IRIS_LOG_DIR if "logs" in lower else NATIVE_LAUNCHER_LOG)
        return {"reply": "J’ouvre les logs IRIS.", "summary": build_summary(), "result": result}
    if any(x in lower for x in ["ouvre le dossier iris", "open companion", "dossier compagnon"]):
        return {"reply": "J’ouvre le dossier du companion.", "summary": build_summary(), "result": open_path(BASE)}
    return None

def ollama_chat(message: str, history: list[dict[str, str]] | None, scene: str) -> str:
    if len(message.strip()) <= 12 and message.lower().strip() in {"salut", "bonjour", "hello", "yo", "hey"}:
        return "Salut. Je suis là. Tu peux me parler, me demander un statut, changer de mode, ou lancer une veille."
    model = choose_chat_model()
    if not model:
        return quick_summary()
    summary = build_summary()
    system = (
        "Tu es IRIS, assistant local sur Mac. "
        "Réponds en français, ton calme, direct, utile, 2 à 4 phrases maximum. "
        f"Mode actuel: {summary['mode']}. Services en ligne: {summary['services_ok']}/{summary['services_total']}. "
        f"Agent en veille active: {summary.get('watch_current') or 'aucun site précis'}. "
        f"Scène du compagnon: {SCENE_LABELS.get(scene, scene)}. "
        "Ne dis pas que tu es un modèle, parle comme IRIS."
    )
    messages = [{"role": "system", "content": system}]
    if history:
        for item in history[-8:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    try:
        r = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.45, "num_predict": 220},
            },
            timeout=60,
        )
        if r.ok:
            data = r.json()
            content = data.get("message", {}).get("content") or data.get("response") or ""
            if content:
                return content.strip()
    except Exception:
        pass
    return quick_summary()

@app.get("/", response_class=HTMLResponse)
def root():
    return FileResponse(UI) if UI.exists() else HTMLResponse("<h1>IRIS v3</h1>")

@app.get("/health")
def health():
    return {"ok": True, "port": read_port()}

@app.get("/api/health")
def api_health():
    services = build_services()
    return {"ok": True, "port": read_port(), "services": services, "models": build_models(), "summary": build_summary(services=services)}

@app.get("/api/core-config")
def api_core_config():
    return JSONResponse(read_core_config())

@app.get("/api/bridge-state")
def api_bridge_state():
    return JSONResponse(build_bridge_state())

@app.get("/api/ready")
def api_ready():
    return JSONResponse(build_ready_state())

@app.post("/api/core/select/{core}")
def api_core_select(core: str):
    config = read_core_config()
    if core not in config["cores"]:
      return JSONResponse({"ok": False, "error": "core inconnu", **config}, status_code=404)
    config["active"] = core
    return JSONResponse(write_core_config(config))

@app.get("/api/summary")
def api_summary():
    return JSONResponse(build_summary())

@app.get("/api/diagnostics")
def api_diagnostics():
    return JSONResponse(build_diagnostics())

@app.get("/api/state")
@app.get("/api/live")
@app.get("/api/dashboard")
@app.get("/api/telemetry")
@app.get("/api/mission-control")
def api_state():
    return JSONResponse(build_state())

@app.get("/api/watch-radar")
@app.get("/api/watch")
def api_watch():
    s = build_state()
    return JSONResponse({
        "watch": s["watch"],
        "watch_queue": s["watch_queue"],
        "current_site": s["watch"]["current_site"],
        "next_site": s["watch"]["next_site"],
        "preview": s["watch"]["preview"],
        "watch_sites_count": s["watch"]["watch_sites_count"],
        "incubator": s["incubator"],
        "chief_focus": s["chief_focus"],
        "projects": s["projects"],
        "selected_project": s["selected_project"],
        "startup_proposals": s["startup_proposals"],
    })

@app.get("/api/services")
@app.get("/api/service-mesh")
def api_services():
    s = build_state()
    return JSONResponse({"services": s["services"], "models": s["models"]})

@app.get("/api/models")
def api_models():
    return JSONResponse(build_models())

@app.get("/api/agents-live")
@app.get("/api/agents")
def api_agents():
    return JSONResponse({"agents": build_agents()})

@app.get("/api/projects")
def api_projects():
    projects, selected_project, priority_project = build_projects()
    return JSONResponse({
        "projects": projects,
        "selected_project": selected_project,
        "priority_project": priority_project,
    })

@app.post("/api/project/select/{project}")
def api_project_select(project: str):
    result = select_project(project)
    status = 200 if result.get("ok") else 404
    return JSONResponse(result, status_code=status)

@app.post("/api/open-project/{project}")
def api_open_project(project: str):
    projects, _selected_project, _priority_project = build_projects()
    item = next((entry for entry in projects if entry["project"] == project), None)
    if not item:
        return JSONResponse({"result": {"ok": False, "stderr": "projet inconnu"}}, status_code=404)
    return JSONResponse({"result": open_path(Path(item["folder_path"]))})

@app.get("/api/timeline")
def api_timeline():
    return JSONResponse({"timeline": build_state()["timeline"]})

@app.get("/api/log")
def api_log(agent: str = Query("watchdog"), errors_only: int = 0):
    return JSONResponse(agent_log(agent, bool(errors_only)))

@app.get("/api/log/{slug}")
def api_log_slug(slug: str, errors_only: int = 0):
    return JSONResponse(agent_log(slug, bool(errors_only)))

def agent_log(slug: str, errors_only: bool = False) -> dict[str, Any]:
    item = next((x for x in AGENTS if x[1] == slug), None)
    if not item:
        return {"slug": slug, "summary": "agent inconnu", "lines": [], "text": ""}
    p = latest_existing(item[2])
    lines = tail(p, 240)
    if errors_only:
        lines = [x for x in lines if is_error(x)]
    summary = f"lignes: {len(lines)} · erreurs détectées: {sum(1 for x in lines if is_error(x))} · dernière ligne: {(lines[-1] if lines else 'n/a')[:120]}"
    return {"slug": slug, "summary": summary, "lines": lines, "text": "\n".join(lines), "path": str(p) if p else None}

@app.post("/api/action")
async def api_action(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    action = data.get("action", "refresh")
    return JSONResponse({"result": run_action(action), "summary": build_summary()})

@app.post("/api/action/{action}")
def api_action_path(action: str):
    if action == "open_native_shell":
        return JSONResponse({"result": spawn_action(action), "summary": build_summary()})
    return JSONResponse({"result": run_action(action), "summary": build_summary()})

@app.post("/api/open-url")
async def api_open_url(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    url = (data.get("url") or "").strip()
    return JSONResponse({"result": spawn_url_in_browser(url)})

@app.get("/api/voice/status")
def api_voice_status():
    return JSONResponse(build_voice_runtime())

@app.post("/api/voice/stop")
def api_voice_stop():
    return JSONResponse(stop_local_voice())

@app.post("/api/voice/speak")
async def api_voice_speak(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    text = (data.get("text") or "").strip()
    voice = (data.get("voice") or "").strip() or None
    return JSONResponse(speak_local_voice(text, voice=voice))

@app.post("/api/voice/transcribe")
async def api_voice_transcribe(request: Request):
    language = (request.query_params.get("lang") or "auto").strip() or "auto"
    audio_bytes = await request.body()
    return JSONResponse(transcribe_local_audio(audio_bytes, language=language))

@app.post("/api/open-path/{target}")
def api_open_path(target: str):
    mapping = {
        "launcher-log": NATIVE_LAUNCHER_LOG,
        "iris-logs": IRIS_LOG_DIR,
        "native-logs": NATIVE / "logs",
        "companion-root": BASE,
        "server-error-log": BASE / "logs" / "server.err.log",
        "server-output-log": BASE / "logs" / "server.out.log",
    }
    path = mapping.get(target)
    if not path:
        return JSONResponse({"result": {"ok": False, "stderr": "cible inconnue"}}, status_code=404)
    return JSONResponse({"result": open_path(path)})

@app.post("/api/restart-backend")
def api_restart_backend():
    return JSONResponse({"result": spawn_companion_restart(), "summary": build_summary()})

@app.post("/api/chat")
async def api_chat(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    scene = (data.get("scene") or "roam").strip()
    speak = bool(data.get("speak"))
    voice = (data.get("voice") or "").strip() or None
    if not message:
        return JSONResponse({"reply": "Je t’écoute.", "summary": build_summary()})
    direct = handle_direct_command(message)
    if direct:
        payload = dict(direct)
        if speak and payload.get("reply"):
            payload["voice_result"] = speak_local_voice(str(payload["reply"]), voice=voice)
        return JSONResponse(payload)
    reply = ollama_chat(message, history, scene)
    payload = {"reply": reply, "summary": build_summary()}
    if speak and reply:
        payload["voice_result"] = speak_local_voice(reply, voice=voice)
    return JSONResponse(payload)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=read_port(), log_level="warning")

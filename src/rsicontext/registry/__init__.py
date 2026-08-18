"""Declarative registry and read-only acquisition planning."""

from rsicontext.registry.loader import load_registry
from rsicontext.registry.planning import DownloadPlan, build_download_plan
from rsicontext.registry.preflight import PreflightReport, run_preflight
from rsicontext.registry.schema import Registry, RegistryEntry
from rsicontext.registry.serving import (
    ServingProfile,
    build_serve_command,
    load_serving_profiles,
    validate_run_binding,
)

__all__ = [
    "DownloadPlan",
    "PreflightReport",
    "Registry",
    "RegistryEntry",
    "ServingProfile",
    "build_download_plan",
    "build_serve_command",
    "load_registry",
    "load_serving_profiles",
    "run_preflight",
    "validate_run_binding",
]

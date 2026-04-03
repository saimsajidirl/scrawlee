"""Shared Loguru instance for scrawleemation (use `pkg` extra for host-app filters)."""

from loguru import logger

log = logger.bind(pkg="scrawleemation")

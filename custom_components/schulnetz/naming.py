"""Naming helpers for the Schulnetz integration."""

from __future__ import annotations

from .const import (
    DEFAULT_DEVICE_NAME_TEMPLATE,
    DEFAULT_EXAM_NAME_TEMPLATE,
)


def split_segments(subject: str) -> list[str]:
    """Split a raw subject identifier into dash-separated segments."""
    return [part.strip() for part in subject.split("-") if part.strip() != ""]


def render_template(template: str, context: dict[str, str]) -> str:
    """Replace {placeholder} tokens in a template with values from context."""
    result = template
    for key, value in context.items():
        result = result.replace("{" + key + "}", str(value))
    return result.strip()


def subject_context(subject: str, aliases: dict[str, str]) -> dict[str, str]:
    """Build the placeholder context for a subject."""
    segments = split_segments(subject)
    context: dict[str, str] = {"full": subject, "alias": aliases.get(subject, "")}
    for idx, seg in enumerate(segments, start=1):
        context[f"seg{idx}"] = seg
    context["last"] = segments[-1] if segments else subject
    context["first"] = segments[0] if segments else subject
    return context


def subject_display_name(
    subject: str,
    aliases: dict[str, str],
    device_template: str | None = None,
) -> str:
    """Resolve the display name for a subject."""
    alias = aliases.get(subject)
    if alias:
        return alias
    template = device_template or DEFAULT_DEVICE_NAME_TEMPLATE
    name = render_template(template, subject_context(subject, aliases))
    return name or subject


def exam_display_name(
    subject: str,
    exam_name: str,
    exam_date: str,
    subject_display: str,
    aliases: dict[str, str],
    exam_template: str | None = None,
) -> str:
    """Resolve the display name for an exam."""
    template = exam_template or DEFAULT_EXAM_NAME_TEMPLATE
    context = subject_context(subject, aliases)
    context["subject"] = subject_display
    context["exam"] = exam_name
    context["date"] = exam_date
    name = render_template(template, context)
    return name or exam_name


def parse_aliases(raw: str | None) -> dict[str, str]:
    """Parse a 'raw = alias' text block into a mapping."""
    aliases: dict[str, str] = {}
    if not raw:
        return aliases
    for line in raw.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            aliases[key] = value
    return aliases

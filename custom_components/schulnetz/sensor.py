"""Sensor platform for the Schulnetz integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    CONF_DEVICE_NAME_TEMPLATE,
    CONF_EXAM_NAME_TEMPLATE,
    CONF_SUBJECT_ALIASES,
    COORDINATOR,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import SchulnetzCoordinator
from .naming import exam_display_name, parse_aliases, subject_display_name

_LOGGER = logging.getLogger(__name__)


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _is_pending(note: Any) -> bool:
    value = str(note).strip().lower()
    return note is None or value in ("---", "hidden", "note hidden", "")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SchulnetzCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    options = entry.options
    aliases = parse_aliases(options.get(CONF_SUBJECT_ALIASES))
    device_template = options.get(CONF_DEVICE_NAME_TEMPLATE)
    exam_template = options.get(CONF_EXAM_NAME_TEMPLATE)

    entities: list[SensorEntity] = []
    data = coordinator.data
    subjects = data.get("subjects", []) if data else []

    for subject in subjects:
        raw = subject.get("subject") or "Unbekannt"
        display = subject_display_name(raw, aliases, device_template)
        slug = slugify(raw)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, slug)},
            name=display,
            manufacturer=MANUFACTURER,
            model="Subject",
        )

        entities.append(
            SchulnetzAverageSensor(
                coordinator, entry.entry_id, raw, display, device_info
            )
        )

        for exam in subject.get("exams", []):
            exam_name = exam.get("name") or "Unbekannt"
            exam_date = exam.get("date") or ""
            exam_display = exam_display_name(
                raw,
                exam_name,
                exam_date,
                display,
                aliases,
                exam_template,
            )
            entities.append(
                SchulnetzExamSensor(
                    coordinator,
                    entry.entry_id,
                    raw,
                    exam_date,
                    exam_name,
                    exam_display,
                    device_info,
                )
            )

    async_add_entities(entities)


class _SchulnetzSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SchulnetzCoordinator,
        entry_id: str,
        raw_subject: str,
        device_info: DeviceInfo,
    ) -> None:
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._raw_subject = raw_subject
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success

    def _find_subject(self) -> dict[str, Any] | None:
        data = self._coordinator.data
        if not data:
            return None
        for subject in data.get("subjects", []):
            if subject.get("subject") == self._raw_subject:
                return subject
        return None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class SchulnetzAverageSensor(_SchulnetzSensor):
    def __init__(
        self,
        coordinator: SchulnetzCoordinator,
        entry_id: str,
        raw_subject: str,
        display: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, entry_id, raw_subject, device_info)
        self._attr_unique_id = f"schulnetz_{slugify(raw_subject)}_average"
        self._attr_name = f"{display} Durchschnitt"

    @property
    def native_value(self) -> float | None:
        subject = self._find_subject()
        if subject is None:
            return None
        return _to_float(subject.get("average"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        subject = self._find_subject()
        if subject is None:
            return {}
        exams = subject.get("exams", [])
        pending = sum(1 for e in exams if _is_pending(e.get("note")))
        return {
            "subject": subject.get("subject"),
            "exam_count": len(exams),
            "pending_exams": pending,
        }


class SchulnetzExamSensor(_SchulnetzSensor):
    def __init__(
        self,
        coordinator: SchulnetzCoordinator,
        entry_id: str,
        raw_subject: str,
        exam_date: str,
        exam_name: str,
        exam_display: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator, entry_id, raw_subject, device_info)
        self._exam_date = exam_date
        self._exam_name = exam_name
        key = slugify(f"{exam_date} {exam_name}")
        self._attr_unique_id = f"schulnetz_{slugify(raw_subject)}_{key}"
        self._attr_name = exam_display

    def _find_exam(self) -> dict[str, Any] | None:
        subject = self._find_subject()
        if subject is None:
            return None
        for exam in subject.get("exams", []):
            if (
                exam.get("date") == self._exam_date
                and exam.get("name") == self._exam_name
            ):
                return exam
        return None

    @property
    def state(self) -> str:
        exam = self._find_exam()
        if exam is None:
            return "unknown"
        note = exam.get("note")
        if _is_pending(note):
            return "offen"
        value = _to_float(note)
        if value is None:
            return "offen"
        return f"{value:g}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        exam = self._find_exam()
        if exam is None:
            return {}
        note = exam.get("note")
        pending = _is_pending(note)
        return {
            "name": exam.get("name"),
            "date": exam.get("date"),
            "weight": exam.get("weight"),
            "got_points": exam.get("got_points"),
            "max_points": exam.get("max_points"),
            "class_average": exam.get("class_average"),
            "note": note,
            "pending": pending,
            "subject": self._raw_subject,
        }

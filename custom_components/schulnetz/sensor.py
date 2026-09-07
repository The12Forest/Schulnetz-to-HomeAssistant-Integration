"""Sensor platform for the Schulnetz integration."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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

# (scraper json key, unique_id suffix, German display label)
_EXAM_VALUE_SENSORS: list[tuple[str, str, str]] = [
    ("weight", "weight", "Gewichtung"),
    ("gotPoints", "got_points", "Punkte"),
    ("classAverage", "class_average", "Klassenschnitt"),
]


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _is_pending(note: Any) -> bool:
    value = str(note).strip().lower()
    return note is None or value in ("---", "hidden", "note hidden", "")


def _parse_date(raw: Any) -> date | None:
    if not raw:
        return None
    match = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", str(raw).strip())
    if not match:
        return None
    day, month, year = (int(match.group(i)) for i in (1, 2, 3))
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


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
                SchulnetzGradeSensor(
                    coordinator,
                    entry.entry_id,
                    raw,
                    exam_date,
                    exam_name,
                    exam_display,
                    device_info,
                )
            )
            entities.append(
                SchulnetzExamDateSensor(
                    coordinator,
                    entry.entry_id,
                    raw,
                    exam_date,
                    exam_name,
                    exam_display,
                    device_info,
                )
            )
            for json_key, uid_suffix, label in _EXAM_VALUE_SENSORS:
                entities.append(
                    SchulnetzExamValueSensor(
                        coordinator,
                        entry.entry_id,
                        raw,
                        exam_date,
                        exam_name,
                        exam_display,
                        device_info,
                        json_key,
                        uid_suffix,
                        label,
                    )
                )
            if _to_float(exam.get("maxPoints")) is not None:
                entities.append(
                    SchulnetzExamValueSensor(
                        coordinator,
                        entry.entry_id,
                        raw,
                        exam_date,
                        exam_name,
                        exam_display,
                        device_info,
                        "maxPoints",
                        "max_points",
                        "Max. Punkte",
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


class _SchulnetzExamSensor(_SchulnetzSensor):
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
        self._base_unique_id = f"schulnetz_{slugify(raw_subject)}_{key}"

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


class SchulnetzGradeSensor(_SchulnetzExamSensor):
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
        super().__init__(
            coordinator, entry_id, raw_subject, exam_date, exam_name, exam_display, device_info
        )
        self._attr_unique_id = f"{self._base_unique_id}_grade"
        self._attr_name = exam_display

    @property
    def native_value(self) -> float | None:
        exam = self._find_exam()
        if exam is None:
            return None
        note = exam.get("note")
        if _is_pending(note):
            return None
        return _to_float(note)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        exam = self._find_exam()
        if exam is None:
            return {}
        note = exam.get("note")
        return {
            "name": exam.get("name"),
            "date": exam.get("date"),
            "note": note,
            "pending": _is_pending(note),
            "subject": self._raw_subject,
        }


class SchulnetzExamDateSensor(_SchulnetzExamSensor):
    _attr_device_class = SensorDeviceClass.DATE

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
        super().__init__(
            coordinator, entry_id, raw_subject, exam_date, exam_name, exam_display, device_info
        )
        self._attr_unique_id = f"{self._base_unique_id}_date"
        self._attr_name = f"{exam_display} Datum"

    @property
    def native_value(self) -> date | None:
        exam = self._find_exam()
        if exam is None:
            return None
        return _parse_date(exam.get("date"))


class SchulnetzExamValueSensor(_SchulnetzExamSensor):
    def __init__(
        self,
        coordinator: SchulnetzCoordinator,
        entry_id: str,
        raw_subject: str,
        exam_date: str,
        exam_name: str,
        exam_display: str,
        device_info: DeviceInfo,
        json_key: str,
        uid_suffix: str,
        label: str,
    ) -> None:
        super().__init__(
            coordinator, entry_id, raw_subject, exam_date, exam_name, exam_display, device_info
        )
        self._json_key = json_key
        self._attr_unique_id = f"{self._base_unique_id}_{uid_suffix}"
        self._attr_name = f"{exam_display} {label}"

    @property
    def native_value(self) -> float | None:
        exam = self._find_exam()
        if exam is None:
            return None
        return _to_float(exam.get(self._json_key))

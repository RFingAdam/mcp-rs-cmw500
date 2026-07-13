"""Coexistence sweep engine: aggressor conditions x victim channels -> matrix.

The validated coex workflow drives an LTE uplink/downlink as the *aggressor*
while measuring a BLE receiver's PER sensitivity (the *victim*) across data
channels, optionally with an aggressor-off baseline row. This module models that
as a resumable sweep: a plan expands into an ordered grid of measurement points,
and `step()` advances the grid a bounded number of points at a time so a long run
stays interruptible and observable across MCP tool calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..driver.cmw500_driver import CMW500Driver
from ..models.band_plans import (
    earfcn_to_frequencies,
    generate_ble_channels,
    generate_lte_earfcns,
)

BASELINE_LABEL = "BASELINE_AGGRESSOR_OFF"


@dataclass
class AggressorCondition:
    """One aggressor state applied for a block of victim measurements."""

    label: str
    technology: str = "NONE"  # "LTE" | "NONE" (baseline)
    band: int | None = None
    earfcn: int | None = None
    dl_mhz: float | None = None
    ul_mhz: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "technology": self.technology,
            "band": self.band,
            "earfcn": self.earfcn,
            "dl_mhz": self.dl_mhz,
            "ul_mhz": self.ul_mhz,
        }


@dataclass
class VictimSpec:
    """BLE receiver-PER victim configuration."""

    channel_start: int = 1
    channel_end: int = 38
    channel_spacing: int = 1
    packets: int = 100
    start_power_dbm: float = -50.0
    coarse_step_db: float = 5.0
    fine_step_db: float = 1.0
    target_per_pct: float = 10.0
    max_tx_dbm: float = -30.0
    skip_adv: bool = True

    def channels(self) -> list[int]:
        return generate_ble_channels(
            self.channel_start, self.channel_end, self.channel_spacing, self.skip_adv
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_start": self.channel_start,
            "channel_end": self.channel_end,
            "channel_spacing": self.channel_spacing,
            "packets": self.packets,
            "start_power_dbm": self.start_power_dbm,
            "coarse_step_db": self.coarse_step_db,
            "fine_step_db": self.fine_step_db,
            "target_per_pct": self.target_per_pct,
            "max_tx_dbm": self.max_tx_dbm,
        }


@dataclass
class SweepPlan:
    """An expanded coex sweep: ordered aggressor conditions x victim channels."""

    conditions: list[AggressorCondition]
    victim: VictimSpec
    aggressor_technology: str = "LTE"

    @property
    def channels(self) -> list[int]:
        return self.victim.channels()

    @property
    def total_points(self) -> int:
        return len(self.conditions) * len(self.channels)

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggressor_technology": self.aggressor_technology,
            "conditions": [c.to_dict() for c in self.conditions],
            "victim": self.victim.to_dict(),
            "channels": self.channels,
            "total_points": self.total_points,
        }


def build_lte_ble_plan(
    lte_bands: list[int],
    earfcn_spacing: int,
    victim: VictimSpec,
    include_baseline: bool = True,
) -> SweepPlan:
    """Expand LTE bands (aggressor) x BLE channels (victim) into a SweepPlan."""
    conditions: list[AggressorCondition] = []
    if include_baseline:
        conditions.append(AggressorCondition(label=BASELINE_LABEL, technology="NONE"))
    for band in lte_bands:
        for earfcn in generate_lte_earfcns(band, earfcn_spacing):
            _b, dl, ul = earfcn_to_frequencies(earfcn)
            conditions.append(
                AggressorCondition(
                    label=f"LTE_B{band}_CH{earfcn}",
                    technology="LTE",
                    band=band,
                    earfcn=earfcn,
                    dl_mhz=dl,
                    ul_mhz=ul,
                )
            )
    return SweepPlan(conditions=conditions, victim=victim, aggressor_technology="LTE")


class CoexSweep:
    """Resumable execution state for a coex sweep."""

    def __init__(self, sweep_id: str, plan: SweepPlan, host: str, port: int) -> None:
        self.sweep_id = sweep_id
        self.plan = plan
        self.host = host
        self.port = port
        self.cursor = 0  # flat index into conditions x channels
        self.long_rows: list[dict[str, Any]] = []
        self.recovery_events: list[str] = []
        self._configured = False
        self._active_band: int | None = None
        self._active_condition_label: str | None = None

    # -- progress helpers -------------------------------------------------------

    @property
    def total(self) -> int:
        return self.plan.total_points

    @property
    def done(self) -> bool:
        return self.cursor >= self.total

    def _locate(self, index: int) -> tuple[AggressorCondition, int]:
        n = len(self.plan.channels)
        condition = self.plan.conditions[index // n]
        channel = self.plan.channels[index % n]
        return condition, channel

    # -- execution --------------------------------------------------------------

    async def _ensure_configured(self, cmw: CMW500Driver) -> None:
        if not self._configured:
            await cmw.ble_sig_clear()
            await cmw.ble_sig_set_packets(self.plan.victim.packets)
            self._configured = True

    async def _setup_condition(self, cmw: CMW500Driver, cond: AggressorCondition) -> None:
        """Apply an aggressor condition (idempotent per condition label)."""
        if cond.label == self._active_condition_label:
            return
        # Imported lazily to avoid a tools<->coex import cycle at module load.
        from ..tools.lte_rx import wait_for_lte_attach

        if cond.technology == "LTE" and cond.band is not None:
            if cond.band != self._active_band:
                await cmw.lte_set_operating_band(cond.band)
                self._active_band = cond.band
            if cond.earfcn is not None:
                await cmw.lte_set_earfcn(cond.earfcn, "DL")
            state = ""
            try:
                state = (await cmw.lte_ps_state()).strip()
            except Exception:  # noqa: BLE001 - transient during band switch
                state = ""
            if "ATT" not in state:
                attached, _ = await wait_for_lte_attach(cmw)
                if not attached:
                    self.recovery_events.append(f"{cond.label}: LTE attach failed during setup")
        self._active_condition_label = cond.label

    async def step(self, cmw: CMW500Driver, max_points: int = 1) -> dict[str, Any]:
        """Run up to ``max_points`` victim measurements, advancing the cursor."""
        from ..tools.bluetooth_signaling import recover_ble_link, run_ble_rx_sensitivity

        await self._ensure_configured(cmw)
        v = self.plan.victim
        ran = 0
        while ran < max_points and not self.done:
            cond, channel = self._locate(self.cursor)
            await self._setup_condition(cmw, cond)

            result = await run_ble_rx_sensitivity(
                cmw,
                channel=channel,
                start_power_dbm=v.start_power_dbm,
                coarse_step=v.coarse_step_db,
                fine_step=v.fine_step_db,
                target_pct=v.target_per_pct,
                max_tx_dbm=v.max_tx_dbm,
            )
            if result.status == "drop":
                self.recovery_events.append(
                    f"{cond.label} ch{channel}: BLE link drop; attempting recovery"
                )
                recovered = await recover_ble_link(cmw, v.start_power_dbm, v.start_power_dbm + 15.0)
                if recovered:
                    result = await run_ble_rx_sensitivity(
                        cmw,
                        channel=channel,
                        start_power_dbm=v.start_power_dbm,
                        coarse_step=v.coarse_step_db,
                        fine_step=v.fine_step_db,
                        target_pct=v.target_per_pct,
                        max_tx_dbm=v.max_tx_dbm,
                    )

            self.long_rows.append(
                {
                    **cond.to_dict(),
                    "ble_channel": channel,
                    "ble_frequency_mhz": result.frequency_mhz,
                    "status": result.status,
                    "ble_sensitivity_dbm": result.sensitivity_dbm,
                    "target_per_pct": v.target_per_pct,
                }
            )
            self.cursor += 1
            ran += 1

        return self.result(include_long=False)

    # -- results ----------------------------------------------------------------

    def matrix(self) -> dict[str, Any]:
        """Assemble a rows(condition) x columns(channel) sensitivity matrix."""
        channels = self.plan.channels
        by_label: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in self.long_rows:
            label = row["label"]
            if label not in by_label:
                by_label[label] = {
                    "label": label,
                    "technology": row["technology"],
                    "band": row["band"],
                    "earfcn": row["earfcn"],
                    "dl_mhz": row["dl_mhz"],
                    "ul_mhz": row["ul_mhz"],
                    "cells": {},
                }
                order.append(label)
            by_label[label]["cells"][str(row["ble_channel"])] = row["ble_sensitivity_dbm"]
        return {"columns": channels, "rows": [by_label[label] for label in order]}

    def result(self, include_long: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "sweep_id": self.sweep_id,
            "status": "complete" if self.done else "running",
            "progress": {
                "done": self.cursor,
                "total": self.total,
                "percent": round(100.0 * self.cursor / self.total, 1) if self.total else 100.0,
            },
            "matrix": self.matrix(),
            "recovery_events": self.recovery_events,
        }
        if include_long:
            data["long"] = self.long_rows
        return data

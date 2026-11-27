# Session 18 — The resistivity meter: build guide, safety checklist and import

Model and effort: Opus 5.5, high.

## Goal

The owner has a build guide for the 4-electrode OhmPi v2024 meter of decision 0042 with
current prices, the app refuses a sounding's readings unless the safety checklist passed
first (hard rule 3), and a sounding's files from the meter come into the app as a record.

## Read

- `docs/BRIEF.md` § 5; `docs/MASTER_PLAN.md` § 4.7, § 4.8; decisions 0036, 0042.
- `docs/knowledge/field-instruments.md` (Resistivity, Positioning).
- The OhmPi v2024 documentation (`https://ohmpi.gitlab.io/ohmpi/`): measurement board
  v2024, power supply (DPH5005), the field checklist PDF, the data file format.
- `src/subphora/domain/field.py` (`ObservationKind`), `web/src/field/`.

## Build

1. `hardware/GUIA.md`, in Spanish for the owner (add it to AGENTS.md's list of Spanish
   files): the bill of materials with current prices and suppliers in Spain or the EU
   (measurement board v2024 from the KiCad files, Raspberry Pi, DPH5005, two 12 V
   batteries, reels, stainless electrodes, enclosure, fuse, emergency stop, signs), the
   build in order, the resistor-board check before any field use, and the Schlumberger
   spacings to use. The licences: CERN-OHL-S-2.0 hardware, GPL-3.0 software, used as they
   are; Subphora never imports OhmPi's code.
2. Safety (hard rule 3), in config and code: the DPH5005 limit at 50 V and 48 mA in the
   guide's OhmPi configuration; a checklist domain model (frozen, `extra="forbid"`) whose
   items come from `config/defaults/` (nobody touching electrodes or cables while
   injecting, signs out, people and animals clear, no rain or standing water on cables,
   insulation checked, fuse in place, emergency stop tested, voltage and current caps read
   on the meter, a second person present or informed) and that passes only with every
   item ticked, a time and the operator; the PWA screen that fills it offline.
3. A sounding record: a new `ObservationKind` for a resistivity sounding (point, array,
   spacings, apparent resistivities, current and voltage per reading, the meter's file
   hash) imported from OhmPi's output file. The import refuses a file with no passed
   checklist attached, or whose checklist time is after the first reading.
4. Calibration plan in the guide: a sounding centred on one of the owner's wells with a
   known level and log, to be done live (VERIFY-LIVE(ves-calibration)).
5. Tests: the import refuses without a checklist, with a failed or late one, and accepts a
   recorded OhmPi file (fixture with its sidecar note); the checklist cannot pass with an
   item unticked; offline entry and retry (browser).

## DO NOT BUILD

- Starting or controlling a measurement from the app; the inversion (session 19); ERT,
  multiplexer boards, HVSR, VLF, RTK, loggers.

## Done when

- `make check` is green, the guide prices every part with its supplier, and the import of
  the fixture is refused without a passed checklist and accepted with one.

Copyright (c) 2026 Almoon-D. All rights reserved.

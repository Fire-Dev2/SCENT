#!/usr/bin/env python3
"""
SCENT acquisition.

Runs one trial of the three-phase protocol and writes a single record.

    baseline   30 s   clean-air stabilization before the sample is introduced
    exposure   60 s   sample headspace present
    purge     120 s   active exhaust, sensors returning to baseline

All channels are sampled at 1 Hz. Each phase is reduced to the arithmetic
mean of its samples, so one trial yields one value per channel per phase.
The analyses reported in the accompanying manuscript use the exposure-phase
columns.

Hardware
    MQ-3, MQ-9, MQ-135   analog, via ADS1115 on A0/A1/A2
    BME680               temperature, relative humidity
    CCS811               eCO2, TVOC

Note on the CCS811: the environmental compensation register (ENV_DATA, 0x05)
is deliberately never written, so the TVOC and eCO2 outputs are independent of
the BME680 readings.

Usage
    python3 acquisition.py --trial 1 --scent ethanol --outdir data
"""

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import board
import busio
import adafruit_ccs811
import adafruit_bme680
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

BASELINE_S = 30
EXPOSURE_S = 60
PURGE_S = 120
SAMPLE_HZ = 1.0

CHANNELS = ["tvoc", "eco2", "temp_c", "humidity_pct", "mq3_v", "mq9_v", "mq135_v"]
PHASES = ["baseline", "exposure", "purge"]


def parse_args():
    p = argparse.ArgumentParser(description="Run one SCENT trial.")
    p.add_argument("--trial", required=True, help="trial identifier")
    p.add_argument("--scent", required=True, help="analyte label")
    p.add_argument("--outdir", default="data")
    return p.parse_args()


def wait_ccs_ready(ccs):
    """Block until the CCS811 has a new sample, so reads are never stale."""
    while not ccs.data_ready:
        time.sleep(0.05)


def read_all(ccs, bme, mq3, mq9, mq135):
    wait_ccs_ready(ccs)
    return {
        "tvoc": ccs.tvoc,
        "eco2": ccs.eco2,
        "temp_c": bme.temperature,
        "humidity_pct": bme.relative_humidity,
        "mq3_v": mq3.voltage,
        "mq9_v": mq9.voltage,
        "mq135_v": mq135.voltage,
    }


def collect_phase(sensors, duration):
    """Sample every channel at SAMPLE_HZ for `duration` seconds."""
    samples = []
    interval = 1.0 / SAMPLE_HZ
    end = time.monotonic() + duration
    next_t = time.monotonic()
    while time.monotonic() < end:
        if time.monotonic() >= next_t:
            samples.append(read_all(*sensors))
            next_t += interval
        time.sleep(0.01)
    return samples


def reduce_samples(samples):
    """Arithmetic mean per channel. Missing readings are skipped."""
    if not samples:
        return {k: None for k in CHANNELS}
    out = {}
    for k in CHANNELS:
        vals = [s[k] for s in samples if s.get(k) is not None]
        out[k] = mean(vals) if vals else None
    return out


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fname = outdir / f"trial_{args.trial}_{args.scent}.csv"

    i2c = busio.I2C(board.SCL, board.SDA)
    ccs = adafruit_ccs811.CCS811(i2c)
    bme = adafruit_bme680.Adafruit_BME680_I2C(i2c)
    ads = ADS.ADS1115(i2c)
    ads.gain = 1
    sensors = (ccs, bme,
               AnalogIn(ads, ADS.P0),   # MQ-3
               AnalogIn(ads, ADS.P1),   # MQ-9
               AnalogIn(ads, ADS.P2))   # MQ-135

    wait_ccs_ready(ccs)

    reduced = {
        "baseline": reduce_samples(collect_phase(sensors, BASELINE_S)),
        "exposure": reduce_samples(collect_phase(sensors, EXPOSURE_S)),
        "purge":    reduce_samples(collect_phase(sensors, PURGE_S)),
    }

    header = ["trial", "scent", "utc"]
    header += [f"{phase}_{ch}" for ch in CHANNELS for phase in PHASES]

    row = [args.trial, args.scent,
           datetime.now(timezone.utc).isoformat(timespec="seconds")]
    row += [reduced[phase][ch] for ch in CHANNELS for phase in PHASES]

    with open(fname, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow(row)

    print(f"Wrote {fname}")


if __name__ == "__main__":
    main()
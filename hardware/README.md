# Hardware

Design files for the SCENT chamber and sensor wiring.

| File | What it is |
|---|---|
| `SCENT_chamber.stl` | Sensor chamber, binary STL, 21,512 triangles |
| `SCENT_wiring.fzz` | Fritzing sketch — the full wiring, editable source |
| `SCENT_wiring_breadboard.png` | Breadboard view exported from that sketch |

## Chamber

Printed in PETG. The mesh bounding box is **161.0 × 101.6 × 200.0** model
units; STL stores no unit, and the model was authored in millimetres.

Open `SCENT_chamber.stl` in any slicer. No supports were used for the
reported build.

## Wiring

`SCENT_wiring.fzz` opens in [Fritzing](https://fritzing.org). Parts in the sketch. The Fritzing library names the ADS1115, BME680 and
CCS811 parts after Adafruit because those are the symbols it ships; the units
actually built with were generic equivalents, as `BOM.csv` records:

| Part | Role |
|---|---|
| Raspberry Pi 5 | acquisition host, I²C master |
| ADS1115 | 16-bit I²C ADC, reads the three MOS dividers on A0/A1/A2 |
| MQ-3 breakout | alcohols |
| MQ-9 breakout | combustible aliphatics, CO |
| Gas sensor breakout (MQ-135) | air quality, NH₃ |
| BME680 breakout | in-chamber temperature and relative humidity |
| CCS811 breakout | eCO2 and TVOC — logged, excluded from every analysis |
| 2-pin fan | active purge exhaust |
| Momentary push button | trial start |

Wire colours in the breadboard view:

| Colour | Carries |
|---|---|
| Red | 5.5 V supply |
| Purple | 3.3 V supply |
| Blue | ground |
| Orange | analogue output from the MOS breakouts to the ADS1115 |
| Green | I²C address lines |
| Grey | I²C serial data |
| Brown | slow control adapter lines |

The MOS breakouts run at 5 V and reach the Pi only through the ADS1115, so
no 5 V line touches a Pi GPIO pin. The BME680 and CCS811 are 3.3 V I²C
devices on the Pi's own bus.

## Bill of materials

`BOM.csv` — thirteen line items totalling **USD 83.00**, which is the figure
quoted in the manuscript.

| Category | USD |
|---|---|
| Compute (Pi 5 1 GB, PSU, microSD) | 53.00 |
| Sensors (3 × MQ, BME680, CCS811) | 15.80 |
| Electronics (ADS1115, fan, button, breadboard and wire) | 5.95 |
| Chamber (PETG, 750 g at $11/kg) | 8.25 |
| **Total** | **83.00** |

Read it with these caveats, which belong in the manuscript too:

- **Component cost only.** No shipping, tax, soldering iron, printer or
  laptop. The build assumes you already have a 3D printer.
- **Sourcing.** Everything but the Raspberry Pi came from AliExpress. The
  sensor breakouts are generic rather than Adafruit or SparkFun parts, which
  is most of why the sensing array comes to $15.80; the equivalent
  Adafruit units would roughly treble that line.
- **Not calibrated parts.** Generic MOS breakouts carry no calibration
  certificate and unit-to-unit variation is not characterised here. The
  classification results are for the specific units built, which is already
  a stated limitation.
- **Prices move.** The Pi 5 1 GB exists at $45 because memory prices rose;
  the same pressure moves the other lines. Quote the figure with its date.
- **Filament is the softest line.** 750 g at $0.011/g is the amount of PETG
  attributed to one chamber. If that is a spool purchased rather than the
  mass the slicer reports for this print, the per-device figure is lower and
  the total falls below 83.

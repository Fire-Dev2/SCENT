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

`SCENT_wiring.fzz` opens in [Fritzing](https://fritzing.org). Parts in the
sketch:

| Part | Role |
|---|---|
| Raspberry Pi 5 | acquisition host, I²C master |
| Adafruit ADS1115 | 16-bit I²C ADC, reads the three MOS dividers on A0/A1/A2 |
| MQ-3 breakout | alcohols |
| MQ-9 breakout | combustible aliphatics, CO |
| Gas sensor breakout (MQ-135) | air quality, NH₃ |
| Adafruit BME680 | in-chamber temperature and relative humidity |
| Adafruit CCS811 | eCO2 and TVOC — logged, excluded from every analysis |
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

Not yet deposited. Quantities and suppliers are in the manuscript; a
machine-readable BOM will be added here.

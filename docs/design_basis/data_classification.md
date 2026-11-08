# Data classification

Every parameter belongs to one of these classes. The manufacturer-data register shows the class for each item. Do not treat one class as another.

| Class | Meaning | Examples | How it is handled |
|---|---|---|---|
| Standard-based method | An equation from a standard or published method | IEC 60909 short-circuit equations, IEEE 80 grid resistance, adiabatic cable withstand, three-phase voltage drop | Implemented in code, tested against independent hand calculations. The standards register lists editions as NOT_VERIFIED |
| Reference data | A published constant or factor | IEC 60909 voltage factors c, copper resistivity and temperature coefficient, cable constant k | Status REFERENCE, source named, edition to be verified. Never presented as manufacturer-confirmed |
| Preliminary assumption | A value chosen by the project owner or master prompt so the package can run | IT load, 3 x 2,000 kVA generators, 3,150 kVA transformers, UPS efficiency point, derating factors of 1.00 | Status ASSUMPTION, listed in the assumptions register, flagged for verification where a data sheet will replace it |
| Manufacturer data | A value only a manufacturer's data sheet or test report can give | Transformer impedance, generator reactance, PRP and ESP ratings, UPS efficiency curve, breaker curves, switchgear ratings | Left empty (status MANUFACTURER_DATA) until supplied. Results that need it show NOT VERIFIED |
| Project / site data | A value from the utility, a survey or the project design | Utility fault levels and X/R, soil resistivity, grid geometry, earth-fault current | Left empty (USER_INPUT) until supplied. Not substituted by a default |

Supplied data goes in `config/manufacturer_data_overrides.yaml` through `import-manufacturer-data`. The master configuration and the code are not edited.

# Register maps

**No vendor register addresses ship with PowerTrace AI.** Not Caterpillar's, not
anyone else's. This directory holds the import format and a blank template.

## Why

A register map is the translation between a controller's Modbus address space and
engineering values. Getting it wrong does not fail loudly — it decodes into
plausible, wrong numbers. A scale factor of 1 where the device uses 0.1 turns
4160 V into 41600 V, which is obvious; the same error on a 0.1 psi oil pressure
scale turns 58 psi into 580 psi, which a tired technician at 03:00 may not catch.
Word order is worse: swap it on a FLOAT32 and you get a number that is the right
order of magnitude and completely wrong.

So the application refuses to guess. It ships nothing, requires you to cite where
each address came from, and flags every value read through an unverified map.

## Getting a real map

Take the addresses from your controller's own published register list — the
manufacturer's Modbus/communication manual for your exact model and firmware
revision. Record the document number and revision in `source_document`; the API
will not let you mark a map verified without it.

Then check it before you trust it: read several values whose true value you can
see on the controller's own display, and confirm they agree. Voltage, frequency
and engine hours are good candidates because a wrong scale or word order on any
of them is immediately visible.

## CSV format

```
parameter_name,address,function_code,data_type,word_order,length,scale,offset,unit,description,bit_position,normalized_key,source
```

| Column | Required | Notes |
|---|---|---|
| `parameter_name` | yes | Unique within the map |
| `address` | yes | As the manufacturer documents it. Mind the 0-based vs 1-based (40001) convention your device uses |
| `function_code` | yes | 1 coils, 2 discrete inputs, 3 holding, 4 input. **Write codes are rejected** |
| `data_type` | yes | `INT16` `UINT16` `INT32` `UINT32` `FLOAT32` `FLOAT64` `BIT` `STRING` |
| `word_order` | for 32/64-bit | `BIG` (high word first) or `LITTLE`. Never guessed |
| `length` | for `STRING` | Registers to read |
| `scale`, `offset` | no | Engineering value = raw × scale + offset. Default 1 and 0 |
| `unit` | no | `V` `A` `Hz` `kW` `kVAr` `kVA` `rpm` `psi` `degC` `%` `h` |
| `bit_position` | for `BIT` | 0–15 within the register |
| `normalized_key` | no | Maps this register onto the normalized model (see below). Leave blank and the parameter is available under its own name only |
| `source` | yes in practice | The document and page the address came from |

## Normalized keys

Setting `normalized_key` is what puts a value on the dashboard and live screens
instead of leaving it as a raw named parameter. The catalogue is in
`app/services/normalization.py`:

```
generator   voltage_L1_L2 voltage_L2_L3 voltage_L3_L1 voltage_L1_N
            current_L1 current_L2 current_L3 frequency rpm
            kw kvar kva power_factor breaker_status engine_status generator_status
engine      oil_pressure coolant_temperature fuel_level battery_voltage
            engine_speed engine_hours
controller  control_voltage breaker_close_command breaker_closed_feedback
```

Discrete I/O named `DO_07`, `DI_11`, `AI_04` and so on is grouped automatically —
its meaning is site-specific, so it is grouped rather than named.

## Importing

```bash
curl -X POST "http://localhost:8000/api/register-maps" \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"name":"EMCP 4.4 site map","manufacturer":"...","model":"...",
          "source_document":"<manual number and revision>"}'

curl -X POST "http://localhost:8000/api/register-maps/1/import" \
     -H "Authorization: Bearer $TOKEN" -F "file=@my-map.csv"

curl -X POST "http://localhost:8000/api/register-maps/1/verify?verified_by=your.name" \
     -H "Authorization: Bearer $TOKEN"
```

A row missing an address or with an invalid data type is rejected with its line
number — nothing is defaulted. Re-importing clears the verified flag, because the
content changed and nobody has checked the new content yet.

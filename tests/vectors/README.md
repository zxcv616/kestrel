# Independent packet fixtures

`packets.json` is a frozen, shared fixture set: 16 valid and 32 invalid packets.
Both C and Python consume it; builds never regenerate its bytes or expected values.
`tools/vector_header.py` only translates JSON literals into C initializers.

The authoring reference, `tools/reference_vectors.py`, deliberately imports no
production codec. It constructs fields with integer-to-byte conversion and
computes CRC by polynomial long division using generator 0x11021. Production C
uses a bytewise bit loop; Python uses the standard-library binascii.crc_hqx.
All three agree with the CRC-16/CCITT-FALSE check `123456789` -> 0x29B1.

## Independently inspectable NOOP

`19 00 c0 00 00 06 00 00 00 00 00 96 7f`

- 0x1900 = version 0, command type 1, secondary header present, APID 0x100.
- 0xc000 = unsegmented, sequence 0.
- 0x0006 = seven bytes after the primary header, minus one. Total: 13 bytes.
- Next four bytes = timestamp 0 milliseconds.
- Next byte = function 0x00, NOOP; no arguments.
- Last two bytes = 0x967f, the independent polynomial remainder over the first
  eleven bytes with the 0xffff initial state.

Coverage includes every telemetry type and all six commands; signed extrema;
unavailable-sensor sentinels; timestamp/counter maxima; HK rate endpoints;
truncation at every position of a NOOP; contradictory header/CRC errors;
wrong APIDs, functions, lengths, flags and arguments; and 256/257-byte inputs.
Sequence rollover is exercised independently for every APID in C and Python.
The cross-language test additionally uses a fixed seed for 1,100 generated cases
(valid ATT/EVENT packets and single-bit corruptions), comparing decoded fields,
re-encoded bytes and exact rejection status.

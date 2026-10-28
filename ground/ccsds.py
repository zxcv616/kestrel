"""Kestrel CCSDS wire codec. No transport, mode authorization or fault execution."""
import binascii
from dataclasses import dataclass
import struct

MAX_PACKET = 256
SCHEMAS = {
    0x010: ("HK", ">BIHBhIIHIBHHHHHH", ("mode", "uptime_s", "battery_mv", "battery_percent",
                                  "temperature_centi_c", "accepted", "rejected", "last_fault", "dropped_events", "task_stalled_mask", "stack_link", "stack_command", "stack_mode", "stack_telemetry", "stack_sensors", "stack_watchdog")),
    0x011: ("ATT", ">hhh", ("x", "y", "z")),
    0x012: ("EVENT", ">HBii", ("id", "severity", "parameter_1", "parameter_2")),
    0x013: ("ACK", ">HB", ("command_sequence", "status")),
}
COMMANDS = {0: ("NOOP", ">B"), 1: ("SET_MODE", ">BB"), 2: ("RESET_COUNTERS", ">B"),
            3: ("SET_HK_RATE", ">BH"), 4: ("REQUEST_HK", ">B"), 5: ("INJECT_FAULT", ">BB")}
APIDS = (*SCHEMAS, 0x100)


class PacketError(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__(status)


@dataclass(frozen=True)
class Packet:
    apid: int
    sequence: int
    time_ms: int
    fields: dict


def crc16(data):
    return binascii.crc_hqx(data, 0xFFFF)


def _integer(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise PacketError("BAD_ARGUMENT")
    return value


def _command(function, argument):
    _integer(function, 0, 255)
    if function not in COMMANDS:
        raise PacketError("UNKNOWN_FUNCTION")
    _integer(argument, 0, 65535)
    if ((function in (0, 2, 4) and argument != 0)
            or (function == 1 and argument not in (1, 2))
            or (function == 3 and not 250 <= argument <= 10000)
            or (function == 5 and not 1 <= argument <= 10)):
        raise PacketError("BAD_ARGUMENT")
    return COMMANDS[function][1]


def encode(packet):
    _integer(packet.apid, 0, 2047)
    if packet.apid not in APIDS:
        raise PacketError("UNKNOWN_APID")
    _integer(packet.sequence, 0, 16383)
    _integer(packet.time_ms, 0, 0xFFFFFFFF)
    try:
        if packet.apid == 0x100:
            if set(packet.fields) != {"function", "argument"}:
                raise PacketError("BAD_ARGUMENT")
            function, argument = packet.fields["function"], packet.fields["argument"]
            fmt = _command(function, argument)
            payload = struct.pack(fmt, function, *([argument] if function in (1, 3, 5) else []))
        else:
            _, fmt, names = SCHEMAS[packet.apid]
            if set(packet.fields) != set(names) or any(type(packet.fields[n]) is not int for n in names):
                raise PacketError("BAD_ARGUMENT")
            payload = struct.pack(fmt, *(packet.fields[name] for name in names))
    except (KeyError, TypeError, struct.error, OverflowError) as error:
        raise PacketError("BAD_ARGUMENT") from error
    first = 0x0800 | (0x1000 if packet.apid == 0x100 else 0) | packet.apid
    wire = struct.pack(">HHHI", first, 0xC000 | packet.sequence, len(payload) + 5, packet.time_ms) + payload
    return wire + struct.pack(">H", crc16(wire))


def decode(data):
    if not isinstance(data, (bytes, bytearray)):
        raise PacketError("BAD_ARGUMENT")
    if not 12 <= len(data) <= MAX_PACKET:
        raise PacketError("BAD_LENGTH")
    first, control, length, time_ms = struct.unpack_from(">HHHI", data)
    if length + 7 != len(data):
        raise PacketError("BAD_LENGTH")
    apid = first & 0x7FF
    if first & 0xE800 != 0x0800 or control & 0xC000 != 0xC000:
        raise PacketError("BAD_HEADER")
    if apid in APIDS and (first >> 12) & 1 != (apid == 0x100):
        raise PacketError("BAD_HEADER")
    if crc16(data[:-2]) != struct.unpack_from(">H", data, len(data) - 2)[0]:
        raise PacketError("BAD_CRC")
    if apid not in APIDS:
        raise PacketError("UNKNOWN_APID")
    payload = data[10:-2]
    if apid == 0x100:
        if not payload:
            raise PacketError("BAD_LENGTH")
        function = payload[0]
        if function not in COMMANDS:
            raise PacketError("UNKNOWN_FUNCTION")
        fmt = COMMANDS[function][1]
        if len(payload) != struct.calcsize(fmt):
            raise PacketError("BAD_LENGTH")
        values = struct.unpack(fmt, payload)
        argument = values[1] if len(values) > 1 else 0
        _command(function, argument)
        fields = {"function": function, "argument": argument}
    else:
        _, fmt, names = SCHEMAS[apid]
        if len(payload) != struct.calcsize(fmt):
            raise PacketError("BAD_LENGTH")
        fields = dict(zip(names, struct.unpack(fmt, payload)))
    return Packet(apid, control & 0x3FFF, time_ms, fields)


class Sequences:
    """One sender owns this state; take once when committing a packet for send."""
    def __init__(self):
        self._next = dict.fromkeys(APIDS, 0)

    def take(self, apid):
        if type(apid) is not int or apid not in self._next:
            raise PacketError("UNKNOWN_APID")
        count = self._next[apid]
        self._next[apid] = (count + 1) & 0x3FFF
        return count

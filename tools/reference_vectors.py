"""Independent M1 fixture authoring: integer byte conversion and polynomial division.

Not run by tests/builds. Does not import either codec. Review changes to the
committed JSON as protocol changes, not as an automatic snapshot update.
"""
import json
from pathlib import Path


def reference_crc(data):
    remainder = (int.from_bytes(data, 'big') << 16) ^ (0xFFFF << (8 * len(data)))
    for bit in range(remainder.bit_length() - 1, 15, -1):
        if remainder & (1 << bit):
            remainder ^= 0x11021 << (bit - 16)
    return remainder


def integer(value, width, signed=False):
    return value.to_bytes(width, 'big', signed=signed)


def frame(apid, sequence, time_ms, payload):
    first = apid + 0x0800 + (0x1000 if apid == 0x100 else 0)
    body = (integer(first, 2) + integer(0xC000 + sequence, 2)
            + integer(len(payload) + 5, 2) + integer(time_ms, 4) + payload)
    return body + integer(reference_crc(body), 2)


def main():
    assert reference_crc(b'123456789') == 0x29B1
    valid = []
    def add(name, apid, fields, widths, sequence=0, time_ms=0):
        if apid == 16:
            fields.update(dropped_events=3, task_stalled_mask=8, stack_link=900, stack_command=920, stack_mode=940, stack_telemetry=960, stack_sensors=980, stack_watchdog=1000)
            widths = widths + [4,1,2,2,2,2,2,2]
        values = list(fields.values())
        payload = b''.join(integer(v, abs(w), w < 0) for v, w in zip(values, widths))
        valid.append(dict(name=name, apid=apid, sequence=sequence, time_ms=time_ms,
                          fields=fields, hex=frame(apid, sequence, time_ms, payload).hex()))
    add('hk_nominal',16,dict(mode=2,uptime_s=42,battery_mv=3800,battery_percent=80,
        temperature_centi_c=2000,accepted=7,rejected=2,last_fault=0),[1,4,2,1,-2,4,4,2],7,42000)
    add('hk_unavailable',16,dict(mode=1,uptime_s=0xFFFFFFFF,battery_mv=65535,battery_percent=255,
        temperature_centi_c=-32768,accepted=0xFFFFFFFF,rejected=0,last_fault=5),[1,4,2,1,-2,4,4,2],16383,0xFFFFFFFF)
    add('att_signed_limits',17,dict(x=-32768,y=32767,z=-1),[-2,-2,-2],16383,123456)
    add('att_zero',17,dict(x=0,y=0,z=0),[-2,-2,-2])
    add('event_signed_limits',18,dict(id=65535,severity=2,parameter_1=-2147483648,parameter_2=2147483647),[2,1,-4,-4],12,0xFFFFFFFF)
    add('event_mode_change',18,dict(id=1,severity=0,parameter_1=1,parameter_2=2),[2,1,-4,-4],1,250)
    add('ack_max_sequence',19,dict(command_sequence=16383,status=0),[2,1],2,800)
    add('ack_unidentifiable',19,dict(command_sequence=65535,status=1),[2,1])
    for function, name, argument, widths in [(0,'noop',0,[1]),(1,'set_mode',2,[1,1]),
          (2,'reset_counters',0,[1]),(3,'set_hk_rate',500,[1,2]),(4,'request_hk',0,[1]),
          (5,'inject_fault',9,[1,1]),(3,'hk_rate_min',250,[1,2]),(3,'hk_rate_max',10000,[1,2])]:
        fields=dict(function=function,argument=argument)
        payload=integer(function,1)+(integer(argument,widths[1]) if len(widths)>1 else b'')
        valid.append(dict(name=name,apid=256,sequence=0 if function==0 else 16383,
            time_ms=0,fields=fields,hex=frame(256,0 if function==0 else 16383,0,payload).hex()))
    invalid=[]
    def bad(name,raw,error): invalid.append(dict(name=name,hex=raw.hex(),error=error))
    noop=bytes.fromhex(next(v['hex'] for v in valid if v['name']=='noop'))
    for length in range(len(noop)): bad(f'truncated_{length}',noop[:length],'BAD_LENGTH')
    def changed(name,offset,value,error,fix_crc=True):
        b=bytearray(noop);b[offset]=value
        if fix_crc:b[-2:]=integer(reference_crc(b[:-2]),2)
        bad(name,bytes(b),error)
    changed('bad_crc',12,noop[12]^1,'BAD_CRC',False)
    changed('wrong_version',0,0x39,'BAD_HEADER')
    changed('missing_secondary_header',0,0x11,'BAD_HEADER')
    changed('segmented',2,0x80,'BAD_HEADER')
    changed('wrong_type',0,0x09,'BAD_HEADER')
    changed('unknown_apid',1,1,'UNKNOWN_APID')
    changed('unknown_function',10,6,'UNKNOWN_FUNCTION')
    changed('declared_length',5,7,'BAD_LENGTH')
    changed('header_before_crc',0,0x39,'BAD_HEADER',False)
    bad('trailing_byte',noop+b'\x00','BAD_LENGTH')
    bad('empty_command',frame(256,0,0,b''),'BAD_LENGTH')
    bad('extra_noop_argument',frame(256,0,0,b'\x00\x01'),'BAD_LENGTH')
    bad('short_hk',frame(16,0,0,b'\x00'*19),'BAD_LENGTH')
    bad('bad_mode',frame(256,0,0,b'\x01\x03'),'BAD_ARGUMENT')
    bad('hk_rate_below',frame(256,0,0,b'\x03\x00\xf9'),'BAD_ARGUMENT')
    bad('hk_rate_above',frame(256,0,0,b'\x03\x27\x11'),'BAD_ARGUMENT')
    bad('bad_fault_id',frame(256,0,0,b'\x05\x00'),'BAD_ARGUMENT')
    bad('oversized_257',frame(256,0,0,b'\x00'*245),'BAD_LENGTH')
    bad('max_256_wrong_payload',frame(256,0,0,b'\x00'*244),'BAD_LENGTH')
    path=Path(__file__).resolve().parents[1]/'tests/vectors/packets.json'
    path.write_text(json.dumps(dict(provenance='Independent integer/polynomial reference; see README.md',valid=valid,invalid=invalid),indent=2)+'\n')
    print(f'{len(valid)} valid / {len(invalid)} invalid vectors. NOOP: {noop.hex()}')


if __name__=='__main__':main()

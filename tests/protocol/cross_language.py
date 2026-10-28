"""Compare actual C decode/re-encode against Python and frozen reference fixtures."""
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ground.ccsds import Packet, PacketError, decode, encode


def main():
    fixtures=json.loads((ROOT/'tests/vectors/packets.json').read_text())
    wires=[v['hex'] for v in fixtures['valid']+fixtures['invalid']]
    randomizer=random.Random(0x4B455354)
    for _ in range(500):
        fields={'x':randomizer.randint(-32768,32767),'y':randomizer.randint(-32768,32767),'z':randomizer.randint(-32768,32767)}
        wire=encode(Packet(17,randomizer.randrange(16384),randomizer.randrange(2**32),fields))
        wires.append(wire.hex())
        changed=bytearray(wire);changed[randomizer.randrange(len(wire))]^=1<<randomizer.randrange(8)
        wires.append(changed.hex())
    for _ in range(100):
        fields={'id':randomizer.randrange(65536),'severity':randomizer.randrange(256),
                'parameter_1':randomizer.randint(-2**31,2**31-1),'parameter_2':randomizer.randint(-2**31,2**31-1)}
        wires.append(encode(Packet(18,randomizer.randrange(16384),randomizer.randrange(2**32),fields)).hex())
    run=subprocess.run([sys.argv[1]],input='\n'.join(wires)+'\n',capture_output=True,text=True,timeout=20,check=True)
    actual=[json.loads(line) for line in run.stdout.splitlines()]
    if len(actual)!=len(wires):raise AssertionError('C probe omitted results')
    for wire,observed in zip(wires,actual):
        try:
            packet=decode(bytes.fromhex(wire))
            expected=dict(apid=packet.apid,sequence=packet.sequence,time_ms=packet.time_ms,
                          fields=packet.fields,hex=encode(packet).hex())
        except PacketError as error:expected={'error':error.status}
        if expected!=observed:raise AssertionError((wire,expected,observed))
    print(f'PASS: {len(wires)} C/Python comparisons, including independent fixtures and seeded mutations')


if __name__=='__main__':main()

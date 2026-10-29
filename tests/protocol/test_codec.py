import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ground.ccsds import APIDS, Packet, PacketError, Sequences, crc16, decode, encode
VECTORS = json.loads((ROOT / 'tests/vectors/packets.json').read_text())


class Packets(unittest.TestCase):
    def test_independent_vectors_both_directions(self):
        for v in VECTORS['valid']:
            with self.subTest(vector=v['name']):
                packet=Packet(v['apid'],v['sequence'],v['time_ms'],v['fields'])
                self.assertEqual(encode(packet).hex(),v['hex'])
                self.assertEqual(decode(bytes.fromhex(v['hex'])),packet)

    def test_housekeeping_fields_in_each_mode(self):
        vectors=json.loads((ROOT / 'tests/vectors/hk_modes.json').read_text())['valid']
        for vector in vectors:
            with self.subTest(mode=vector['name']):
                packet=decode(bytes.fromhex(vector['hex']))
                self.assertEqual(packet.fields,vector['fields'])
                self.assertEqual(packet.time_ms,42000)
                self.assertEqual(packet.fields['uptime_s'],42)

    def test_invalid_vectors_and_error_precedence(self):
        for v in VECTORS['invalid']:
            with self.subTest(vector=v['name']):
                with self.assertRaises(PacketError) as error:
                    decode(bytes.fromhex(v['hex']))
                self.assertEqual(error.exception.status,v['error'])

    def test_crc_check_value_and_empty(self):
        self.assertEqual(crc16(b'123456789'),0x29B1)
        self.assertEqual(crc16(b''),0xFFFF)

    def test_wire_ranges_reject_without_truncation(self):
        cases=[Packet(256,16384,0,{'function':0,'argument':0}),
               Packet(256,-1,0,{'function':0,'argument':0}),
               Packet(256,0,2**32,{'function':0,'argument':0}),
               Packet(17,0,0,{'x':32768,'y':0,'z':0}),
               Packet(17,0,0,{'x':True,'y':0,'z':0}),
               Packet(256,0,0,{'function':1,'argument':3}),
               Packet(256,0,0,{'function':0,'argument':1}),
               Packet(256,0,0,{'function':0,'argument':0,'extra':3})]
        for packet in cases:
            with self.subTest(packet=packet),self.assertRaises(PacketError):encode(packet)


class SequenceTests(unittest.TestCase):
    def test_independent_apids_wrap_at_16384(self):
        state=Sequences()
        for n in range(16386):
            for apid in APIDS:self.assertEqual(state.take(apid),n&16383)
        self.assertEqual(state.take(16),2)
        self.assertEqual(state.take(16),3)
        self.assertEqual(state.take(17),2)
        with self.assertRaises(PacketError):state.take(0)
        self.assertEqual(state.take(16),4)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SequenceTests if '--sequences' in sys.argv else Packets)
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

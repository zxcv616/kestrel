"""Translate frozen JSON fixtures to C initializers; never calculate packet bytes."""
import json
from pathlib import Path
import sys

vectors=json.loads(Path(sys.argv[1]).read_text())
lines=['/* Generated from committed fixtures. Do not edit. */',
       'typedef struct { const char *name; uint8_t wire[256]; size_t length; KestrelPacket packet; } ValidVector;',
       'static const ValidVector valid_vectors[] = {']
union={16:'hk',17:'att',18:'event',19:'ack',256:'command'}
for v in vectors['valid']:
    raw=bytes.fromhex(v['hex'])
    fields=', '.join('.'+k+' = '+str(n) for k,n in v['fields'].items())
    lines.append('{"'+v['name']+'", {'+','.join(hex(b) for b in raw)+'}, '+str(len(raw))+
                 ', {.apid='+str(v['apid'])+', .sequence='+str(v['sequence'])+', .time_ms='+str(v['time_ms'])+
                 ', .payload.'+union[v['apid']]+'={'+fields+'}}},')
lines.extend(['};','typedef struct { const char *name; uint8_t wire[257]; size_t length; KestrelStatus expected; } InvalidVector;',
              'static const InvalidVector invalid_vectors[] = {'])
for v in vectors['invalid']:
    raw=bytes.fromhex(v['hex'])
    lines.append('{"'+v['name']+'", {'+(','.join(hex(b) for b in raw) or '0')+'}, '+str(len(raw))+', KESTREL_'+v['error']+'},')
lines.append('};')
Path(sys.argv[2]).write_text('\n'.join(lines)+'\n')

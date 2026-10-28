const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const sandbox = {};
vm.runInNewContext(fs.readFileSync(path.join(root,'dashboard/web/packet-codec.js'),'utf8'),sandbox);
const codec = sandbox.KestrelPackets;
const vectors=JSON.parse(fs.readFileSync(path.join(root,'tests/vectors/packets.json'),'utf8'));
for (const vector of vectors.valid) {
  const result=JSON.parse(JSON.stringify(codec.inspect(vector.hex)));
  assert.equal(result.ok,true,vector.name);
  assert.deepEqual(result.packet,{apid:vector.apid,sequence:vector.sequence,time_ms:vector.time_ms,fields:vector.fields},vector.name);
  assert.equal(result.crc.valid,true);
}
for (const vector of vectors.invalid) {
  const result=codec.inspect(vector.hex);
  assert.equal(result.ok,false,vector.name);
  assert.equal(result.error,vector.error,vector.name);
}
assert.equal(codec.inspect('xx').error,'BAD_HEX');
assert.equal(codec.inspect('123').error,'BAD_HEX');
assert.equal(codec.inspect('19 00 c0 00 00 06 00 00 00 00 00 96 7f').ok,true);
console.log(`PASS: browser inspector matches ${vectors.valid.length+vectors.invalid.length} independent vectors`);

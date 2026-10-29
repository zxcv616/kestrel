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
// Every mode uses the same HK schema. Also pass the actual decoded bytes through
// the console model, guarding against a SAFE-only display filter or lost time.
vm.runInNewContext(fs.readFileSync(path.join(root,'dashboard/web/console-model.js'),'utf8'),sandbox);
for(const vector of JSON.parse(fs.readFileSync(path.join(root,'tests/vectors/hk_modes.json'),'utf8')).valid){
 const result=JSON.parse(JSON.stringify(codec.inspect(vector.hex)));
 assert.equal(result.ok,true,vector.name);
 assert.deepEqual(result.packet.fields,vector.fields,vector.name);
 const display=sandbox.KestrelConsole.view({running:true,lastPacketAgeSeconds:0,hk:{ageSeconds:0,packet:result.packet},events:[{direction:'rx',hex:vector.hex}]});
 assert.equal(display.mode,vector.fields.mode);
 assert.equal(display.fields.battery_percent,vector.fields.battery_percent);
 assert.equal(display.fields.temperature_centi_c,2000);
 assert.equal(display.fields.uptime_s,42);
 assert.equal(display.time,42000);
}
console.log('PASS: BOOT/SAFE/NOMINAL/LOW_POWER HK bytes decode and reach the display');

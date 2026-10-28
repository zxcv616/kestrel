/* Browser-local inspector. Flight-authoritative codecs remain C and Python. */
(function () {
  'use strict';
  const schemas = {
    16: [['mode',1],['uptime_s',4],['battery_mv',2],['battery_percent',1],['temperature_centi_c',-2],['accepted',4],['rejected',4],['last_fault',2],['dropped_events',4],['task_stalled_mask',1],['stack_link',2],['stack_command',2],['stack_mode',2],['stack_telemetry',2],['stack_sensors',2],['stack_watchdog',2]],
    17: [['x',-2],['y',-2],['z',-2]],
    18: [['id',2],['severity',1],['parameter_1',-4],['parameter_2',-4]],
    19: [['command_sequence',2],['status',1]]
  };
  const fail = status => { throw new Error(status); };
  function bytes(hex) {
    const clean = hex.replace(/\s/g, '');
    if (clean.length > 514) fail('BAD_LENGTH');
    if (clean.length % 2 || /[^0-9a-f]/i.test(clean)) fail('BAD_HEX');
    return Uint8Array.from(clean.match(/../g) || [], pair => parseInt(pair, 16));
  }
  function crc16(data) {
    let crc = 0xffff;
    for (const byte of data) {
      crc ^= byte << 8;
      for (let bit=0; bit<8; bit++) crc = ((crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1) & 0xffff;
    }
    return crc;
  }
  function decode(data) {
    if (data.length < 12 || data.length > 256) fail('BAD_LENGTH');
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    const first=view.getUint16(0), control=view.getUint16(2), apid=first&0x7ff;
    if (view.getUint16(4)+7!==data.length) fail('BAD_LENGTH');
    if ((first&0xe800)!==0x0800 || (control&0xc000)!==0xc000) fail('BAD_HEADER');
    const known=apid===256||Object.hasOwn(schemas,apid);
    if (known && ((first>>12)&1)!==Number(apid===256)) fail('BAD_HEADER');
    if (crc16(data.subarray(0,-2))!==view.getUint16(data.length-2)) fail('BAD_CRC');
    if (!known) fail('UNKNOWN_APID');
    let fields={};
    if (apid===256) {
      if (data.length<13) fail('BAD_LENGTH');
      const fn=data[10];
      if (fn>5) fail('UNKNOWN_FUNCTION');
      const length=fn===3?3:(fn===1||fn===5?2:1);
      if (data.length!==12+length) fail('BAD_LENGTH');
      const argument=length===3?view.getUint16(11):length===2?data[11]:0;
      if ((fn===1 && ![1,2].includes(argument)) || (fn===3 && (argument<250||argument>10000)) || (fn===5 && (argument<1||argument>10))) fail('BAD_ARGUMENT');
      fields={function:fn,argument};
    } else {
      const schema=schemas[apid];
      if (data.length!==12+schema.reduce((total,[,width])=>total+Math.abs(width),0)) fail('BAD_LENGTH');
      let offset=10;
      for (const [name,width] of schema) {
        const method=(width<0?'getInt':'getUint')+(Math.abs(width)*8);
        fields[name]=view[method](offset); offset+=Math.abs(width);
      }
    }
    return {apid,sequence:control&0x3fff,time_ms:view.getUint32(6),fields};
  }
  function inspect(hex) {
    let data;
    try { data=bytes(hex); } catch(error) { return {ok:false,error:error.message,bytes:[]}; }
    const result={bytes:Array.from(data)};
    if (data.length>=12) {
      const received=(data[data.length-2]<<8)|data[data.length-1];
      const calculated=crc16(data.subarray(0,-2));
      result.crc={received,calculated,valid:received===calculated};
    }
    try { return {...result,ok:true,packet:decode(data)}; }
    catch(error) { return {...result,ok:false,error:error.message}; }
  }
  globalThis.KestrelPackets=Object.freeze({bytes,crc16,decode,inspect});
})();

const assert=require('node:assert/strict');
const {view,receipt}=require('../../dashboard/web/console-model.js');
const sample=(mode,age,hkAge=age)=>({running:true,lastPacketAgeSeconds:age,hk:{ageSeconds:hkAge,packet:{time_ms:1000,fields:{mode}}}});
for(const [mode,period] of [[2,1],[1,10],[3,5]]){
 assert.equal(view(sample(mode,period*1.5-.001)).link,'green');
 assert.equal(view(sample(mode,period*1.5)).link,'amber');
 assert.equal(view(sample(mode,period*3)).link,'red');
 assert.equal(view(sample(mode,0,period*1.5)).stale,true,'Fresh ACK must not refresh old HK');
}
assert.equal(view(null).age,null);
assert.equal(view(null).fields,undefined);
assert.equal(view({observation:{mode:2},running:true}).mode,undefined,'Internal observation cannot set mode');
assert.equal(view(sample(2,1),0,2).link,'green','Acknowledged HK rate changes threshold');
assert.equal(view(sample(2,0),4).link,'red','Age advances even if backend disconnects');
const event={packet:{time_ms:2000,fields:{id:1,parameter_2:1}}};
assert.equal(view({...sample(2,0),modeEvents:[event]}).mode,1);
assert.equal(view({...sample(2,0),modeEvents:[{packet:{...event.packet,time_ms:500}}]}).mode,2);
assert.equal(receipt({state:'timeout'}).text,'NO ACK');
assert.equal(receipt({state:'pending'}).text,'PENDING');
assert.equal(receipt({state:'acknowledged',status:'OK'}).text,'ACCEPTED');
assert.equal(receipt({state:'acknowledged',status:'MODE_DENIED'}).text,'REJECTED');
console.log('Console rules: mode thresholds, independent freshness, packet-only mode, command outcomes pass');

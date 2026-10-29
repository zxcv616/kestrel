/* Pure display rules. Spacecraft state is exclusively received packet content. */
(function(root){
 const modes=['BOOT','SAFE','NOMINAL','LOW_POWER'];
 function view(f,elapsed=0,nominalPeriod=1){
  const hk=f?.hk, fields=hk?.packet?.fields;
  const transition=(f?.modeEvents||[]).find(e=>e.packet.fields.id===1);
  const mode=transition&&(!hk||transition.packet.time_ms>hk.packet.time_ms)?transition.packet.fields.parameter_2:fields?.mode;
  const period=mode===1?10:mode===3?5:mode===2?nominalPeriod:null;
  const age=f?.lastPacketAgeSeconds==null?null:f.lastPacketAgeSeconds+elapsed;
  const hkAge=hk?hk.ageSeconds+elapsed:null;
  const stale=!f?.running||hkAge===null||period===null||hkAge>=period*1.5;
  const link=age===null?'waiting':period===null?'waiting':age>=period*3?'red':age>=period*1.5?'amber':'green';
  const rx=(f?.events||[]).filter(e=>e.direction==='rx').at(-1);
  const decoded=rx&&root.KestrelPackets?.inspect(rx.hex);
  const time=decoded?.ok?decoded.packet.time_ms:hk?.packet?.time_ms;
  return {fields,mode,period,age,hkAge,stale,link,time};
 }
 function receipt(row){
  if(['acknowledged','late'].includes(row.state)&&row.status!=null)return {text:row.status==='OK'?'ACCEPTED':'REJECTED',tone:row.status==='OK'?'green':'red',code:row.status};
  return {text:({pending:'PENDING',timeout:'NO ACK',send_failed:'SEND FAILED',cancelled:'CANCELLED'})[row.state]||'PENDING',tone:row.state==='pending'?'':'amber',code:null};
 }
 root.KestrelConsole={view,receipt,modes};
 if(typeof module!=='undefined')module.exports=root.KestrelConsole;
})(typeof globalThis!=='undefined'?globalThis:this);

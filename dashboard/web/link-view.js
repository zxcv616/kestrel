/* Packet animation consumes observed events only; display duration is not link latency. */
class LinkView {
 static reducedPreference=null;
 constructor(root,onInspect){this.root=root;this.onInspect=onInspect;this.session=null;this.last=0;this.queue=[];this.timer=null;this.reduced=LinkView.reducedPreference??matchMedia('(prefers-reduced-motion: reduce)').matches;
 root.innerHTML=`<section class="panel communication"><div class="panel-head"><h2>Communication</h2><label class="motion-control"><input type="checkbox" id="reduce-motion"> Reduce motion</label></div>
 <div class="link-scene"><div class="ground-end"><svg viewBox="0 0 100 100" aria-hidden="true"><path d="M24 25Q24 70 69 70Z" fill="#253e45" stroke="#95d3dc" stroke-width="2"/><path d="M45 55L73 27M65 19l16 16M46 68l-9 20m16-18 12 18M25 90h52" fill="none" stroke="#95d3dc" stroke-width="3"/></svg><strong>Ground station</strong><small>Commands & telemetry</small></div>
 <div class="signal-path"><div class="signal-line"></div><button class="packet-pulse" hidden></button><div class="signal-caption" role="status" aria-live="polite">No packet activity</div></div>
 <div class="satellite-end"><svg viewBox="0 0 180 110" aria-hidden="true"><g class="satellite-body"><path d="M60 35L10 24v50l50 8M120 35l50-11v50l-50 8" fill="#243f50" stroke="#95d3dc" stroke-width="2"/><path d="M25 28v48m18-44v47m94-47v47m18-51v48M10 48l50 9m60 0 50-9" stroke="#54778a"/><path d="M60 25l42-12 20 20-42 13Z" fill="#a4b28a" stroke="#d8ed96"/><path d="M60 25v56l20 17V46Z" fill="#405755" stroke="#a4b28a"/><path d="M80 46l42-13v52L80 98Z" fill="#5c7262" stroke="#d8ed96"/><path d="M90 51l22-7v15l-22 7zm0 24 22-7v12l-22 7z" fill="#203e48"/><path d="M85 18L75 3m34 16 15-16" stroke="#d8ed96" stroke-width="2"/><circle class="satellite-light" cx="71" cy="53" r="3" fill="#d8ed96"/></g></svg><strong>Satellite computer</strong><small class="satellite-state">Stopped</small></div></div>
 <div class="link-bottom"><span>Live packet activity · motion slowed for visibility. Select a packet to inspect its bytes.</span></div>
 <div class="packet-feed" aria-label="Recent live packets"></div></section>`;
 this.pulse=root.querySelector('.packet-pulse');root.querySelector('#reduce-motion').checked=this.reduced;
 root.querySelector('#reduce-motion').addEventListener('change',e=>{this.reduced=e.target.checked;LinkView.reducedPreference=this.reduced;root.classList.toggle('reduced-motion',this.reduced);});root.classList.toggle('reduced-motion',this.reduced);
 this.pulse.onclick=()=>{if(this.current)this.onInspect(this.current)};
 }
 update(f){
 const animateStart=this.wasStopped&&!!f?.running;this.wasStopped=!f?.running;
 const running=!!f?.running, paused=f?.observationAgeSeconds<.5&&!!(f?.observation?.stalledMask&((1<<1)|(1<<4))), healthy=running&&f.state==='connected'&&!f.hk?.stale&&!paused;
 this.root.classList.toggle('link-active',healthy);this.root.classList.toggle('link-warning',running&&!healthy);
 this.root.querySelector('.satellite-state').textContent=!running?'Stopped':paused?'Telemetry paused · see test observation':!healthy?'Waiting / stale':({0:'BOOT',1:'SAFE',2:'NOMINAL',3:'LOW POWER'}[f.hk?.packet?.fields.mode]||'Awaiting HK');
 const events=f?.events||[];
 if(f?.sessionId!==this.session){this.session=f?.sessionId;this.last=events.at(-1)?.id||0;this.queue=[];clearTimeout(this.timer);this.timer=null;this.pulse.hidden=true;this.root.querySelector('.signal-caption').textContent=events.length?'Recent packets below':'No packet activity';if(animateStart){this.queue.push(...events);this.play();}}
 else {const fresh=events.filter(e=>e.id>this.last);if(fresh.length){this.last=fresh.at(-1).id;
 const control=fresh.some(e=>e.direction==='tx'||e.label==='EVENT'||e.label==='ACK');
 if(control){this.queue=[];clearTimeout(this.timer);this.timer=null;this.pulse.hidden=true;}
 const display=control?fresh.filter(e=>e.direction==='tx'||e.label==='EVENT'||e.label==='ACK'||(e.label==='HK'&&e.id>fresh.filter(v=>v.direction==='tx'||v.label==='EVENT'||v.label==='ACK').at(-1).id)):fresh;
 this.queue.push(...display);if(!control)this.queue=this.queue.filter(e=>e.direction==='tx'||e.label==='EVENT'||e.label==='ACK').concat(this.queue.filter(e=>e.label==='HK'||e.label==='ATT').slice(-2));
 this.queue=this.queue.slice(-24);this.play();}}
 if(!running){this.queue=[];clearTimeout(this.timer);this.timer=null;this.pulse.hidden=true;this.root.querySelector('.signal-caption').textContent='Flight stopped';}
 const feed=this.root.querySelector('.packet-feed');const focused=document.activeElement?.dataset?.eventId;
 feed.replaceChildren();for(const e of events.slice(-8).reverse()){const b=document.createElement('button');b.className='packet-chip';b.dataset.eventId=e.id;b.textContent=`${e.direction==='tx'?'↑':'↓'} ${e.label}${e.status?' · '+e.status:''} #${e.sequence}${e.rttMs!==null?' · '+e.rttMs+' ms':''}`;b.title='Inspect actual '+e.hex.length/2+' bytes';b.onclick=()=>this.onInspect(e);feed.append(b);if(focused===String(e.id))b.focus();}
 if(!events.length)feed.textContent=f?.running&&!f.sessionId?'Restart the local Python server to enable packet capture.':'Packets appear here when a flight is running.';
 const latest=f?.history?.[0];const timedOut=latest&&['timeout','send_failed'].includes(latest.state)?latest:null;this.root.classList.toggle('command-warning',!!timedOut);
 if(timedOut&&!this.timer)this.root.querySelector('.signal-caption').textContent=`${timedOut.command.toUpperCase()} #${timedOut.sequence} · ${timedOut.state}`;
 }
 play(){if(this.timer||!this.queue.length)return;const e=this.current=this.queue.shift();const label=`${e.label}${e.status?' · '+e.status:''}${e.rttMs!==null?' · '+e.rttMs+' ms':''}`;this.pulse.textContent=label;this.pulse.hidden=false;this.pulse.className='packet-pulse '+(e.direction==='tx'?'uplink':'downlink');this.pulse.style.animation='none';void this.pulse.offsetWidth;this.pulse.style.animation='';this.root.querySelector('.signal-caption').textContent=(e.direction==='tx'?'Sent: ':'Received: ')+label;
 if(e.label==='HK')document.querySelectorAll('.received-hk .empty-metric').forEach(el=>{el.classList.remove('hk-flash');void el.offsetWidth;el.classList.add('hk-flash');});
 this.timer=setTimeout(()=>{this.timer=null;this.pulse.hidden=true;this.play();},this.reduced?250:850);
 }
 destroy(){clearTimeout(this.timer);this.queue=[];}
}

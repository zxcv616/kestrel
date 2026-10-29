/* Optional demo authoring tool: npm install --no-save playwright, plus Chrome.
 * Start the local console first. Uses only visible UI controls and real packets.
 * Frames go to output/demo; convert them with the command in docs/release.md. */
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.CONSOLE_URL||'http://127.0.0.1:8765');
 await page.getByRole('button',{name:'Start test flight',exact:true}).waitFor();
 await page.evaluate(()=>document.fonts.ready);
 await fs.mkdir('output/demo',{recursive:true});
 const started=performance.now(),frames=[];
 const at=async seconds=>{const delay=started+seconds*1000-performance.now();if(delay>0)await new Promise(r=>setTimeout(r,delay));};
 const capture=(async()=>{let i=0;while(performance.now()-started<30000){await at(i*.25);const file=`frame-${String(i++).padStart(4,'0')}.png`;const time=(performance.now()-started)/1000;await page.screenshot({path:'output/demo/'+file});frames.push({file,time});}})();
 try{
  await at(2);await page.getByRole('button',{name:'Start test flight',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.health-strip').textContent.includes('80%'));
  await at(5);await page.getByRole('button',{name:'Review & send'}).click();
  await at(6);await page.getByRole('button',{name:'Send command',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.mode-banner h1').textContent==='NOMINAL');
  await at(11);await page.locator('#fault-choice').selectOption('2');await page.getByRole('button',{name:'Inject · 5 s'}).click();
  await page.waitForFunction(()=>document.querySelector('.mode-banner h1').textContent==='SAFE');
  await page.waitForFunction(()=>document.querySelector('.event-list').textContent.includes('FAULT CLEARED'));
  await at(20);await page.getByRole('button',{name:'Review & send'}).click();
  await at(21);await page.getByRole('button',{name:'Send command',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.mode-banner h1').textContent==='NOMINAL');
  await capture;
  if(errors.length)throw Error(errors.join('\n'));
  await fs.writeFile('output/demo/frames.txt',frames.map((f,i)=>`file '${f.file}'\nduration ${Math.max(.01,(frames[i+1]?.time??30)-f.time).toFixed(3)}`).join('\n')+`\nfile '${frames.at(-1).file}'\n`);
  console.log(JSON.stringify({frames:frames.length,durationSeconds:30,sequence:'boot, NOMINAL, Command stall, SAFE, FAULT CLEARED, commanded recovery'}));
 }finally{await page.getByRole('button',{name:'Stop',exact:true}).click().catch(()=>{});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

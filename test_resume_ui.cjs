// Exercise resume controls without calling a provider or starting a run.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/ui.js','utf8');
const start=source.indexOf('function resumeNeedsConnection(');
const end=source.indexOf("$('stop').onclick",start);

function fixture(job,configured=false){
 const elements=new Map(),calls=[],messages=[];
 const context=vm.createContext({lastJob:job,configured,connectionOffline:false,busy:false,submitting:false,
  $:id=>{if(!elements.has(id))elements.set(id,{disabled:false,textContent:'',replaceChildren(){}});return elements.get(id);},
  tr:ja=>ja,message:(...args)=>messages.push(args),api:async(...args)=>{calls.push(args);},budgetValue:()=>null,refresh:async()=>{},Date});
 vm.runInContext(source.slice(start,end),context);
 return {context,elements,calls,messages};
}

test('paid resume without a key is disabled and sends no request',async()=>{
 const f=fixture({folder:'fixture',report:{manual_mode:false}});
 vm.runInContext('paintResumeAvailability()',f.context);
 assert.equal(f.elements.get('resume').disabled,true);
 assert.match(f.elements.get('resumeConnectionHelp').textContent,/AI接続/);
 await f.elements.get('resume').onclick();
 assert.equal(f.calls.length,0);
});
test('manual resume does not require an API key',async()=>{
 const f=fixture({folder:'fixture',manual_mode:true,progress:{resume:{reason:null}}});
 vm.runInContext('paintResumeAvailability()',f.context);
 assert.equal(f.elements.get('resume').disabled,false);
 await f.elements.get('resume').onclick();
 assert.equal(f.calls.length,1);
 assert.equal(f.calls[0][0],'start');
});
test('reconnecting enables paid resume and keeps saved-run settings',async()=>{
 const f=fixture({folder:'saved-run',progress:{resume:{reason:'budget'}}});
 f.context.configured=true;
 vm.runInContext('paintResumeAvailability()',f.context);
 assert.equal(f.elements.get('resume').disabled,false);
 await f.elements.get('resume').onclick();
 assert.equal(f.calls[0][1].resume_folder,'saved-run');
 assert.equal(f.calls[0][1].confirm_estimate,true);
});
test('a disconnected page cannot submit paid or manual resume',async()=>{
 for(const manual_mode of [true,false]){
  const f=fixture({folder:'fixture',manual_mode},true);
  f.context.connectionOffline=true;
  vm.runInContext('paintResumeAvailability()',f.context);
  assert.equal(f.elements.get('resume').disabled,true);
  await f.elements.get('resume').onclick();
  assert.equal(f.calls.length,0);
 }
});

test('finish reserve resume keeps the chosen cumulative ceiling',async()=>{
 const f=fixture({folder:'saved-run',progress:{resume:{reason:'finish_reserve'}}},true);
 f.context.budgetValue=()=>3.85;
 await f.elements.get('resume').onclick();
 assert.equal(f.calls[0][1].resume_folder,'saved-run');
 assert.equal(f.calls[0][1].budget_usd,3.85);
 assert.equal(f.calls[0][1].confirm_estimate,false);
});
test('embedded UI stays identical to ui.js',()=>{
 const page=fs.readFileSync(__dirname+'/index.html','utf8');
 assert.equal(page.split('<script>')[1].split('</script>')[0].trim(),source.trim());
 assert.match(page,/id="appVersion"/);
 assert.match(page,/id="resumeConnectionHelp"/);
});

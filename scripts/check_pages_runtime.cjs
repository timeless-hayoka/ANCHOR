// Runtime smoke tests without a browser dependency; browser QA remains separate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {textContent:'', innerHTML:'', value:'', dataset:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){}});
  return nodes.get(id);
}
const context = vm.createContext({
  document:{getElementById:node,querySelectorAll:()=>[],addEventListener(){}},
  window:{addEventListener(){}}, navigator:{}, setInterval:()=>0, clearInterval(){},setTimeout(){},console,
  fetch(){throw new Error('Static console attempted a network request');}
});
const html = fs.readFileSync(path.join(root, 'dist-pages/trinity_hunt.html'), 'utf8');
const script = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n');
vm.runInContext(script, context);
for (const name of ['renderMission','renderGate','renderBoot','renderRecon','renderHistory','renderDossiers','renderArena','renderCvss','renderReport','renderTrinity']) {
  assert.ok(vm.runInContext(`${name}().length > 100`,context),name);
}
assert.equal(vm.runInContext('calcCvss({...cvssState,c:"N",i:"N",a:"N"}).score',context),0);
assert.equal(vm.runInContext('calcCvss({...cvssState}).score',context),9.8);
assert.equal(vm.runInContext('calcCvss({...cvssState,scope:"C",c:"N",i:"N",a:"N"}).score',context),0);
vm.runInContext('loadCase("TinyReentrancy")',context);
assert.match(node('reportPreview').textContent,/ILLUSTRATIVE DEMO DRAFT/);
assert.match(node('reportPreview').textContent,/Reentrancy in TinyReentrancy/);
assert.equal(vm.runInContext('CASES.find(c=>c.validation_state==="UNAVAILABLE").true_negative',context),0);
node('chatInput').value='test';
vm.runInContext('sendChat()',context);
assert.match(vm.runInContext('chatMessages.at(-1).text',context),/No model or server/);
console.log('PASS: console startup, 10 views, CVSS known/zero-impact vectors, case report, untested-state accounting, local chat');

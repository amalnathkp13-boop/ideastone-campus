// Run: node docs/qa/navigation-state.cjs (no packages required).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
    const source = fs.readFileSync(path.join(__dirname, '../../addons/ideastone_campus/static/src/js/navigation_state.js'), 'utf8');
    const {navigationItems, moveNavigation} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
    const catalog = [{id:'home',label:'Home',main:true},{id:'fees',label:'Fees',main:true},{id:'item/receipt',label:'Receipt'}];
    const defaults = navigationItems(catalog);
    assert.deepEqual(defaults.map(row=>row.id), ['home','fees']);
    const saved = [{...defaults[1],label:'My payments'}, {...defaults[0],visible:false},
        {id:'shortcut-1',target:'item/receipt',label:'My receipt',visible:true},
        {id:'shortcut-2',target:'forbidden',label:'Unauthorized',visible:true}];
    assert.deepEqual(navigationItems(catalog,saved).map(row=>row.label), ['My payments','Home','My receipt']);
    assert.equal(navigationItems(catalog,saved)[1].visible,false);
    assert.equal(navigationItems(catalog,[...saved,saved[0]]).length,3);
    assert.deepEqual(navigationItems([...catalog,{id:'library',label:'Library',main:true}],saved).map(row=>row.id), ['fees','home','shortcut-1','library']);
    const revoked = navigationItems(catalog.filter(row=>row.id!=='fees'),saved);
    assert(!revoked.some(row=>row.target==='fees'));
    assert(navigationItems(catalog,defaults.map(row=>({...row,visible:false}))).some(row=>row.visible));
    const removed = navigationItems(catalog,[{...defaults[1],visible:false,removed:true},defaults[0]]);
    assert.equal(removed[0].removed,true);
    moveNavigation(defaults,'fees',0);
    assert.deepEqual(defaults.map(row=>row.id),['fees','home']);
    moveNavigation(defaults,'fees',1);
    moveNavigation(defaults,'missing',0);
    moveNavigation(defaults,'fees',10);
    assert.deepEqual(defaults.map(row=>row.id),['home','fees']);
    assert.deepEqual(navigationItems(catalog).map(row=>row.id),['home','fees']);
    console.log('Navigation reconciliation, permission removal, new modules, ordering and reset checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

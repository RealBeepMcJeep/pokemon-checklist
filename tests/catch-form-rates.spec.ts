import {test,expect,type Page} from '@playwright/test';
import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';
import {readFileSync} from 'node:fs';
const capture = JSON.parse(readFileSync(resolve('data/capture.json'),'utf8')) as {pokemon: {id:number;form:number;name:string;sm:{catchRate:number}|null;usum:{catchRate:number}|null}[]};
const key='pokemon-checklist-catch-selection-v1';
async function open(page:Page,p:string){await page.goto(p==='standalone-file'?pathToFileURL(resolve('index.html')).href:'/');}
test('search and ordered rail retain only forms with distinct stock catch rates in both games',async({page},info)=>{
 await open(page,info.project.name);
 for(const mode of ['sun','ultra-sun']){
  await page.locator('#mode-select').selectOption(mode);await page.locator('#tools-toggle').click();
  await page.locator('#catch-species-name').click();await page.locator('#catch-species').fill('Rattata');
  await expect(page.locator('#catch-species-list [role=option]')).toHaveCount(1);await page.getByRole('option',{name:'Rattata',exact:true}).click();
  await page.locator('#catch-species-rail .selected').press('ArrowRight');await expect(page.locator('#catch-species-name')).toHaveText('Raticate');
  await page.locator('#catch-species-name').click();await page.locator('#catch-species').fill('Minior');
  const game=mode==='sun'?'sm':'usum';const base=capture.pokemon.find(p=>p.id===774&&p.form===0)!;
  const allowed=capture.pokemon.filter(p=>p.id===774&&(p.form===0||p[game]?.catchRate!==base[game]?.catchRate)).sort((a,b)=>a.form-b.form);
  await expect(page.locator('#catch-species-list [role=option]')).toHaveText(allowed.map(p=>p.name));
  await page.getByRole('option',{name:base.name,exact:true}).click();
  for(const p of allowed.slice(1)){await page.locator('#catch-species-rail .selected').press('ArrowRight');await expect(page.locator('#catch-species-name')).toHaveText(p.name);await expect(page.locator('.catch-form-note')).toContainText('base-species icon');}
  await page.getByRole('button',{name:'Close tools'}).click();
 }
});
test('remembered hidden form migrates to its own base with notice and selection-only memory',async({page},info)=>{
 await open(page,info.project.name);await page.evaluate(k=>localStorage.setItem(k,JSON.stringify({id:20,form:1,ball:'Heavy Ball'})),key);await page.reload();await page.locator('#tools-toggle').click();
 await expect(page.locator('#catch-species-name')).toHaveText('Raticate');await expect(page.locator('#catch-ball-name')).toHaveText('Heavy Ball');
 await expect(page.locator('#catch-memory-notice')).toContainText(/form.*base/i);
 expect(await page.evaluate(k=>JSON.parse(localStorage.getItem(k)!),key)).toEqual({id:20,form:0,ball:'Heavy Ball'});
});

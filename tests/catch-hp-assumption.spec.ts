import {test, expect, type Page} from '@playwright/test';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {probability} from '../src/capture';
async function open(page:Page,project:string){await page.goto(project==='standalone-file'?pathToFileURL(resolve('index.html')).href:'/');await page.locator('#tools-toggle').click();}
const odds=(currentHP:number,maxHP:number)=> (probability({currentHP,maxHP,catchRate:190,ballBonus:1,status:'none',caught:0,roto:false}).probability*100).toFixed(2)+'%';
test('one HP diagnoses estimated and entered maxima, preserves exact mode and calculation',async({page},info)=>{
 await open(page,info.project.name);
 const exact=page.getByLabel('Exact HP inputs'), slider=page.getByLabel('HP remaining (approximate %)');
 await page.getByRole('button',{name:'Set 1 HP',exact:true}).click();
 await expect(slider).toHaveAttribute('aria-valuetext',/1 HP.*estimated.*100/i);
 await expect(page.locator('#catch-result strong')).toHaveText(odds(1,100));
 await exact.check();await page.getByLabel('Maximum HP',{exact:true}).fill('200');
 await page.getByLabel('Current HP',{exact:true}).fill('20');await page.getByRole('button',{name:'Set 1 HP',exact:true}).click();
 await expect(exact).toBeChecked();await expect(page.getByLabel('Current HP',{exact:true})).toHaveValue('1');
 await exact.uncheck();await expect(slider).toHaveAttribute('aria-valuetext',/1 HP.*entered.*200/i);
 await expect(page.locator('#catch-result strong')).toHaveText(odds(1,200));
 await slider.fill('50');await expect(page.locator('#catch-result strong')).toHaveText(odds(50,100));
 await slider.fill('1');await exact.check();await expect(page.getByLabel('Current HP',{exact:true})).toHaveValue('1');
 await page.getByLabel('Maximum HP',{exact:true}).fill('0');await expect(page.locator('#catch-error')).toContainText('Maximum HP');
 await exact.uncheck();await expect(slider).toHaveAttribute('aria-valuetext',/invalid.*last valid.*200/i);
 await expect(page.locator('#catch-result strong')).toHaveText(odds(1,200));
});

import {test,expect} from '@playwright/test';import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';
test('compact catch-rate badge follows stock, Heavy Ball, override and invalid or unavailable inputs',async({page},info)=>{
 await page.goto(info.project.name==='standalone-file'?pathToFileURL(resolve('index.html')).href:'/');await page.locator('#tools-toggle').click();
 const badge=page.locator('.catch-rate');await expect(badge).toHaveText('Catch 190');await expect(badge).toHaveAttribute('title',/stock.*190/i);
 await page.locator('#catch-ball-name').click();await page.locator('#catch-ball').fill('Heavy Ball');await page.getByRole('option',{name:'Heavy Ball',exact:true}).click();
 await expect(badge).toHaveText('Catch 170');await expect(badge).toHaveAttribute('title',/Heavy Ball.*170/i);
 await page.getByText('Optional modifiers & hack override',{exact:true}).click();await page.getByLabel('Override stock catch rate').check();await page.getByLabel('Catch rate override (0–255)').fill('45');
 await expect(badge).toHaveText('Catch 25');await expect(badge).toHaveAttribute('title',/override.*45.*Heavy Ball.*25/i);
 await page.getByLabel('Catch rate override (0–255)').fill('999');await expect(badge).toHaveText('Catch —');await expect(badge).toHaveAttribute('title',/catch rate/i);
 await page.getByRole('button',{name:'Close tools'}).click();await page.locator('#mode-select').selectOption('sun');await page.locator('#tools-toggle').click();
 await page.locator('#catch-species-name').click();await page.locator('#catch-species').fill('Poipole');await page.getByRole('option',{name:'Poipole',exact:true}).click();
 await expect(badge).toHaveText('Catch —');await expect(badge).toHaveAttribute('title',/unavailable/i);
});

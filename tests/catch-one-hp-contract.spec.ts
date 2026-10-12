import {test,expect} from '@playwright/test';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

test('one-HP shortcut preserves percentage mode and uses the last-entered maximum',async({page},info)=>{
 await page.goto(info.project.name==='standalone-file'?pathToFileURL(resolve('index.html')).href:'/');
 await page.locator('#tools-toggle').click();
 const exact=page.getByLabel('Exact HP inputs');
 await exact.check();await page.getByLabel('Maximum HP',{exact:true}).fill('200');
 await exact.uncheck();
 await page.getByRole('button',{name:'Set 1 HP',exact:true}).click();
 await expect(exact).not.toBeChecked();
 await expect(page.locator('#catch-calculator input[type=range]')).toHaveValue('1');
 await expect(page.locator('#catch-breakdown')).toContainText('HP 1/200');
 await expect(page.locator('#catch-calculator output')).toContainText('1 HP');
});

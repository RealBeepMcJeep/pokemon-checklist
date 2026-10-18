import {test,expect} from '@playwright/test';import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';
test('vertical mouse movement over neighbor does not accidentally select',async({page},info)=>{
 await page.goto(info.project.name==='standalone-file'?pathToFileURL(resolve('index.html')).href:'/');await page.locator('#tools-toggle').click();
 await expect(page.locator('#tools-panel')).toBeVisible();
 await expect(page.locator('#catch-species-rail button').last()).toBeVisible();
 const before=await page.locator('#catch-species-name').textContent(),b=(await page.locator('#catch-species-rail button').last().boundingBox())!;
 await page.mouse.move(b.x+b.width/2,b.y+20);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+34,{steps:3});await page.mouse.up();
 await expect(page.locator('#catch-species-name')).toHaveText(before!);
 await page.locator('#catch-species-rail button').last().click();await expect(page.locator('#catch-species-name')).toHaveText('Raichu');
});

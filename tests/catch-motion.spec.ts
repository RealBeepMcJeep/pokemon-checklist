import {test,expect,type Page} from '@playwright/test';
import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';
async function open(page:Page,p:string){await page.goto(p==='standalone-file'?pathToFileURL(resolve('index.html')).href:'/');await page.locator('#tools-toggle').click();await expect(page.locator('#catch-species-rail')).toBeVisible();}
const xOf=(page:Page,kind:string)=>page.locator(`#catch-${kind}-rail`).evaluate(el=>(el.querySelector('.catch-visual[data-slot="0"]') ?? el.querySelector('.selected .catch-sprite'))!.getBoundingClientRect().x);
test('mouse drag displaces artwork before release, settles once, cancels short drag and keeps later click',async({page},info)=>{
 await open(page,info.project.name);
 const rail=page.locator('#catch-species-rail'), b=(await rail.boundingBox())!,x=b.x+b.width/2,y=b.y+25;
 const before=await page.locator('#catch-species-name').textContent();const start=await xOf(page,'species');
 await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x-50,y,{steps:5});
 expect(await xOf(page,'species')).toBeLessThan(start-25);await expect(page.locator('#catch-species-name')).toHaveText(before!);
 await page.mouse.up();await expect(page.locator('#catch-species-name')).toHaveText('Raichu');await page.waitForTimeout(350);
 expect(Math.abs(await xOf(page,'species')-start)).toBeLessThan(1);
 await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+20,y,{steps:4});await page.mouse.up();await expect(page.locator('#catch-species-name')).toHaveText('Raichu');
 await rail.locator('button').last().click();await expect(page.locator('#catch-species-name')).toHaveText('Sandshrew');
 await rail.locator('.selected').press('ArrowRight');await rail.locator('.selected').press('ArrowRight');await expect(page.locator('#catch-species-name')).toHaveText('Nidoran♀');
 await expect(rail.locator('button')).toHaveCount(3);
});
test('real touch moves both rails, cancels vertical and multitouch, wraps with reduced motion',async({browser},info)=>{
 const context=await browser.newContext({viewport:{width:390,height:700},hasTouch:true,isMobile:true});const page=await context.newPage();await open(page,info.project.name);const cdp=await context.newCDPSession(page);
 for(const kind of ['species','ball']){
  const rail=page.locator(`#catch-${kind}-rail`);await rail.scrollIntoViewIfNeeded();const b=(await rail.boundingBox())!,x=b.x+b.width*.7,y=b.y+30,start=await xOf(page,kind),before=await page.locator(`#catch-${kind}-name`).textContent();
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-50,y}]});await page.waitForTimeout(50);
  expect(await xOf(page,kind)).toBeLessThan(start-20);await expect(page.locator(`#catch-${kind}-name`)).toHaveText(before!);
  await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await expect(page.locator(`#catch-${kind}-name`)).not.toHaveText(before!);await page.waitForTimeout(350);
  const chosen=await page.locator(`#catch-${kind}-name`).textContent();
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-20,y}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await expect(page.locator(`#catch-${kind}-name`)).toHaveText(chosen!);
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x+3,y:y-65}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await expect(page.locator(`#catch-${kind}-name`)).toHaveText(chosen!);
  await rail.scrollIntoViewIfNeeded();const r=(await rail.boundingBox())!;const tx=r.x+80,ty=r.y+30;
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:tx,y:ty,id:1}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:tx,y:ty,id:1},{x:tx+20,y:ty,id:2}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await expect(page.locator(`#catch-${kind}-name`)).toHaveText(chosen!);
 }
 await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#catch-ball-name').click();await page.locator('#catch-ball').fill('Poké Ball');await page.getByRole('option',{name:'Poké Ball',exact:true}).click();await page.locator('#catch-ball-rail button').first().click();await expect(page.locator('#catch-ball-name')).toHaveText('Beast Ball');await page.locator('#catch-ball-rail .selected').press('ArrowRight');await expect(page.locator('#catch-ball-name')).toHaveText('Poké Ball');
 expect(await page.locator('.catch-visual').first().evaluate(el=>parseFloat(getComputedStyle(el).transitionDuration))).toBeLessThanOrEqual(.001);await context.close();
});

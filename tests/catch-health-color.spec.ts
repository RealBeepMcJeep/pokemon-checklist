import {test,expect} from '@playwright/test';import {pathToFileURL} from 'node:url';import {resolve} from 'node:path';
test('HP range has vivid green, yellow and red thumb and filled track with numeric labels',async({page},info)=>{
 await page.goto(info.project.name==='standalone-file'?pathToFileURL(resolve('index.html')).href:'/');await page.locator('#tools-toggle').click();
 const slider=page.getByLabel('HP remaining (approximate %)');
 for(const [value,color,label] of [['100','rgb(49, 216, 136)','100%'],['50','rgb(255, 211, 90)','50%'],['1','rgb(255, 96, 105)','1 HP']]){
  await slider.fill(value);await expect(page.locator('.catch-health output')).toHaveText(label);
  await expect.poll(()=>slider.evaluate(el=>getComputedStyle(el).accentColor)).toBe(color);
  expect(await slider.evaluate(el=>getComputedStyle(el).backgroundImage)).toContain('linear-gradient');
 }
 await page.emulateMedia({reducedMotion:'reduce'});expect(await slider.evaluate(el=>parseFloat(getComputedStyle(el,'::-webkit-slider-thumb').transitionDuration))).toBeLessThanOrEqual(.001);
});

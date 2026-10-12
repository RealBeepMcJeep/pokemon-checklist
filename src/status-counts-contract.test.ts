import {test,expect} from 'vitest';
import {ENCOUNTERS_BY_MODE} from './data';
import {DEFAULT_MODE,catchNowRows,locationProgress} from './domain';

test('location progress partitions unique catch-now species into none, seen-only and caught',()=>{
 const location=ENCOUNTERS_BY_MODE[DEFAULT_MODE].islands[0].locations[0];
 const rows=catchNowRows(location);
 expect(rows.length).toBeGreaterThanOrEqual(3);
 const caught=rows[0].speciesId!,seen=rows[1].speciesId!;
 const progress=locationProgress(location,id=>id===caught?'caught':id===seen?'seen':'none');
 expect(progress).toEqual({none:rows.length-2,seen:1,caught:1,total:rows.length});
});

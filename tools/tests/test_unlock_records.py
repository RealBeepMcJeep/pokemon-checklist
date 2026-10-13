import unittest
import sys
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pokemon_ops as ops

class UnlockRecords(unittest.TestCase):
    def test_python_and_node_accept_unlock_flags_without_weakening_validation(self):
        try:
            result=ops.validate_record_map({"setting:unlock:tauros":{"s":"on","at":1,"by":"fixture"}},[25])
        except ops.SchemaError as error:
            self.fail(str(error))
        self.assertEqual(result["setting:unlock:tauros"]["s"],"on")
        with self.assertRaises(ops.SchemaError):
            ops.validate_record_map({"setting:unlock:unknown":{"s":"on"}},[25])
        with self.assertRaises(ops.SchemaError):
            ops.validate_record_map({"setting:unlock:tauros":{"s":"none"}},[25])
        root=Path(__file__).resolve().parents[2]
        script='import {validateRecordMap} from "./tools/firebase-admin-rest.mjs";validateRecordMap({"setting:unlock:tauros":"on"});'
        run=subprocess.run(['node','--input-type=module','-e',script],cwd=root,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)

    def test_rule_rejects_old_client_none_and_unknown_unlocks(self):
        root=Path(__file__).resolve().parents[2]
        script="""import fs from 'node:fs';import assert from 'node:assert/strict';
        const rules=JSON.parse(fs.readFileSync('firebase/database.rules.json','utf8'));
        const expr=rules.rules.users['$uid'].state.records?.['$key']?.['.validate']??'true';
        const check=(key,s)=>new Function('$key','newData','return '+expr)({matches:r=>r.test(key)}, {child:()=>({val:()=>s})});
        assert.equal(check('setting:unlock:tauros','on'),true);
        assert.equal(check('setting:unlock:tauros','off'),true);
        assert.equal(check('setting:unlock:tauros','none'),false);
        assert.equal(check('setting:unlock:unknown','on'),false);
        assert.equal(check('species:25','caught'),true);
        """
        run=subprocess.run(['node','--input-type=module','-e',script],cwd=root,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)

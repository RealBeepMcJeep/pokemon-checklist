"""Bounded parse acceleration must preserve existing Showdown block semantics."""
import sys
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import showdown_text as st

class BlockIndexTests(unittest.TestCase):
    def test_different_name_lookups_parse_same_source_once(self):
        source='\n\tindexalpha: {num: 1},\n\tindexbeta: {num: 2},\n'
        with mock.patch.object(st,"top_blocks",wraps=st.top_blocks) as scan:
            self.assertEqual(st.block(source,"indexalpha"),"{num: 1}")
            self.assertEqual(st.block(source,"indexbeta"),"{num: 2}")
            self.assertEqual(scan.call_count,1,"Repeated source scanning is the measured bottleneck")

    def test_first_normalized_duplicate_and_missing_semantics_match_reference(self):
        source='\n\t"foo-bar": {num: 3},\n\tfoobar: {num: 4},\n\ttail: {nested: {x: 2}},\n'
        for name in ["foo-bar","FOO BAR","foobar","tail","missing",""]:
            expected=next((body for key,body in st.top_blocks(source) if st._key(key)==st._key(name)),"")
            self.assertEqual(st.block(source,name),expected)
        self.assertEqual(st.block(source,"foobar"),"{num: 3}")

    def test_changed_content_and_incomplete_tail_do_not_reuse_old_results(self):
        first='\n\tchanging: {num: 11},\n\tbroken: {num: 3'
        second=first.replace("num: 11","num: 12")
        self.assertEqual(st.block(first,"changing"),"{num: 11}")
        self.assertEqual(st.block(second,"changing"),"{num: 12}")
        self.assertEqual(st.block(second,"broken"),"")
        self.assertEqual(st.block("","changing"),"")

    def test_source_retention_is_bounded_and_eviction_reparses(self):
        sources=[f"\n\tevictionprobe: {{num: {i}}},\n" for i in range(9)]
        with mock.patch.object(st,"top_blocks",wraps=st.top_blocks) as scan:
            for source in sources:self.assertTrue(st.block(source,"evictionprobe"))
            self.assertEqual(st.block(sources[0],"evictionprobe"),"{num: 0}")
            self.assertEqual(scan.call_count,10)

if __name__=="__main__":unittest.main()

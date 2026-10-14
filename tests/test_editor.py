import copy
import tempfile
from pathlib import Path
import unittest
import editor_project as editor
from editor_worker import graph


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.doc=editor.new_project()
        self.media=editor.add_media(self.doc,{'path':'sample.mp4','duration':10.,'width':640,'height':360,'audio':True,
            'subtitles':[{'start':1.,'end':8.,'text':'Hello'}], 'censors':[{'start':3.,'end':4.}]})
        self.clip=editor.append_clip(self.doc,self.media)

    def test_trim_speed_split_and_annotation_mapping(self):
        clip=self.doc['clips'][0];clip.update({'in':2.,'out':8.,'speed':2.})
        right=editor.split(self.doc,self.clip,1.)
        self.assertEqual(clip['out'],4.)
        self.assertEqual(self.doc['clips'][1]['in'],4.)
        self.assertEqual(editor.duration(self.doc),3.)
        self.assertEqual(editor.locate(self.doc,1.)[0]['id'],right)
        self.assertEqual(editor.locate(self.doc,1.)[1],4.)
        self.assertIsNone(editor.locate(self.doc,3.))
        self.assertEqual([(e['start'],e['end']) for e in editor.mapped_annotations(self.doc,'subtitles')],[(0.,1.),(1.,3.)])
        self.assertEqual([(e['start'],e['end']) for e in editor.mapped_annotations(self.doc,'censors')],[(.5,1.)])
        self.doc['clips'].reverse()
        self.assertEqual([(e['start'],e['end']) for e in editor.mapped_annotations(self.doc,'censors')],[(2.5,3.)])

    def test_history_snapshots_do_not_change_with_later_edits(self):
        history=editor.History();history.record(self.doc);self.doc['clips'][0]['in']=2.
        old=history.undo(self.doc);self.assertEqual(old['clips'][0]['in'],0.)
        restored=history.redo(old);self.assertEqual(restored['clips'][0]['in'],2.)
        self.assertEqual(self.doc['clips'][0]['in'],2.)

    def test_project_annotations_are_independent_for_repeated_sources(self):
        second=editor.append_clip(self.doc,self.media)
        editor.replace_timeline_annotations(self.doc,'censors',[{'start':12.,'end':13.,'kind':'manual'}])
        self.assertEqual(self.doc['clips'][0]['annotations']['censors'],[])
        self.assertEqual(self.doc['clips'][1]['annotations']['censors'][0]['start'],2.)
        self.doc['clips'].reverse()
        self.assertEqual([(e['start'],e['end']) for e in editor.mapped_annotations(self.doc,'censors')],[(2.,3.)])
        editor.split(self.doc,second,2.5)
        left,right=self.doc['clips'][:2]
        self.assertIsNot(left['annotations'],right['annotations'])
        editor.replace_timeline_annotations(self.doc,'censors',[{'start':2.6,'end':2.9}])
        self.assertEqual(left['annotations']['censors'],[])
        self.assertEqual([(e['start'],e['end']) for e in editor.mapped_annotations(self.doc,'censors')],[(2.6,2.9)])

    def test_annotation_crosses_cut_and_speed_change(self):
        self.doc['clips'][0].update({'in':2.,'out':6.,'speed':2.})
        editor.append_clip(self.doc,self.media)
        editor.replace_timeline_annotations(self.doc,'subtitles',[{'id':'cue','start':1.5,'end':2.5,'source':'Across the cut','translation':'Translated'}])
        values=editor.mapped_annotations(self.doc,'subtitles')
        self.assertEqual([(e['start'],e['end']) for e in values],[(1.5,2.),(2.,2.5)])
        self.assertNotEqual(values[0]['id'],values[1]['id'])
        self.assertEqual(values[1]['translation'],'Translated')

    def test_exact_cut_roundtrip_does_not_create_zero_length_fragments(self):
        editor.append_clip(self.doc,self.media);editor.append_clip(self.doc,self.media)
        for clip,values in zip(self.doc['clips'],[{'in':.95,'out':1.7},{'in':.4,'out':.95},{'in':0.,'out':1.5,'speed':2.}]):clip.update(values)
        editor.replace_timeline_annotations(self.doc,'subtitles',[{'start':.8,'end':1.3,'source':'Ends at the cut'}])
        editor.validate(self.doc)
        self.assertEqual(self.doc['clips'][2]['annotations']['subtitles'],[])
        self.assertEqual([(e['start'],e['end']) for e in editor.mapped_annotations(self.doc,'subtitles')],[(.8,1.3)])

    def test_project_library_preserves_missing_projects_and_deduplicates(self):
        from project_library import remember,recent,describe
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'saved.juicy';editor.save(self.doc,path)
            remember(folder,path);remember(folder,path)
            self.assertEqual(len(recent(folder)),1)
            self.assertEqual(describe(path)['clips'],1)
            self.assertEqual(describe(path)['missing'],1)
            path.unlink()
            self.assertTrue(describe(path)['error'])
            self.assertEqual(len(recent(folder)),1)

    def test_boundary_and_nonfinite_edits_are_rejected(self):
        for start,end in ((-1,3),(4,4),(0,11),(float('nan'),5)):
            with self.subTest(start=start,end=end):
                draft=copy.deepcopy(self.doc);draft['clips'][0].update({'in':start,'out':end})
                with self.assertRaises(ValueError):editor.validate(draft)
        for time in (0.,10.):
            with self.assertRaises(ValueError):editor.split(self.doc,self.clip,time)

    def test_export_graph_normalizes_audio_and_silent_sources(self):
        self.doc['media'][self.media]['audio']=False
        self.doc['clips'][0]['speed']=.25
        inputs,filters,video,audio=graph(self.doc,mute=True)
        self.assertIn('anullsrc',filters)
        self.assertIn('duration=40.0',filters)
        self.assertIn('between(t,12.0,16.0)',filters)
        self.assertEqual(audio,'afinal')
        self.doc['media'][self.media]['audio']=True
        self.assertIn('atempo=0.5,atempo=0.5',graph(self.doc)[1])

    def test_save_load_roundtrip_with_unicode_and_missing_source(self):
        self.doc['name']='Orange · 編集'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.juicy';editor.save(self.doc,path)
            self.assertEqual(editor.load(path),self.doc)


if __name__=='__main__':unittest.main()

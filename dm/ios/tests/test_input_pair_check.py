import importlib.util,unittest,os
from pathlib import Path
P=Path(os.environ.get('PAIR_SOURCE',str(Path(__file__).resolve().parents[1]/'tools/input_pair_check.py')))
spec=importlib.util.spec_from_file_location('pair',P);pair=importlib.util.module_from_spec(spec);spec.loader.exec_module(pair)
def state(lx=0):return dict(buttons=0,lx=lx,ly=0,rx=0,ry=0)
def trace(axis=32767):
 ui=[];hid=[]
 for i,(phase,value) in enumerate([('began',0),('moved',axis),('ended',0)],1):
  n=i*100;v=state(value)
  ui.append(dict(stage='event',eventseq=i,mono_ns=n,source='uitouch',phase=phase,slot=0,touch='0x1',x=90+value/32767*60,y=200,touch_timestamp_s=42.125,mode='game',**v))
  ui.append(dict(stage='output',receiptseq=i,eventseq=i,event_first_seq=i,event_last_seq=i,mono_ns=n+10,publish_end_ns=n+20,source='uitouch',phase=phase,mode='game',**v))
  hid.append(dict(event='npad_return',read_start_ns=n+25,time_ns=n+30,sampling=i,id=32,style=2,attributes=1,script_mask=0,**v))
 return ui,hid
class PairFixtureTests(unittest.TestCase):
 def case(self,f,status,reason=None):
  u,h=trace();f(u,h);g=pair.analyze(u,h,domain='synthetic')
  self.assertEqual(g['status'],status,g);self.assertFalse(g['physical_pass_claimed'],g)
  if reason:self.assertIn(reason,g['reasons'],g)
 def test_01_positive_right(self):self.case(lambda u,h:None,'protocol_pass')
 def test_02_positive_left(self):
  u,h=trace(-32767);g=pair.analyze(u,h);self.assertEqual(g['status'],'protocol_pass');self.assertFalse(g['physical_pass_claimed'])
 def test_03_release(self):
  u,h=trace();g=pair.analyze(u,h);self.assertEqual(g['status'],'protocol_pass');self.assertTrue(g['release_received'])
 def test_04_stale_equal(self):self.case(lambda u,h:h[1].update(read_start_ns=1,time_ns=2),'incomplete','missing_receipt')
 def test_05_invalid_controller_zero(self):self.case(lambda u,h:h[-1].update(id=99,style=0,attributes=0),'incomplete','invalid_controller')
 def test_06_non_touch_output(self):
  def f(u,h):
   u[:]=[dict(stage='output',receiptseq=1,eventseq=0,event_first_seq=0,event_last_seq=0,mono_ns=110,publish_end_ns=120,source='layout',phase='none',mode='game',**state(32767))]
   h[:]=[dict(event='npad_return',read_start_ns=125,time_ns=130,sampling=1,id=32,style=2,attributes=1,script_mask=0,**state(32767))]
  self.case(f,'incomplete','no_touch_pairs')
 def test_07_blank_no_receipt(self):self.case(lambda u,h:h.clear(),'incomplete','missing_receipt')
 def test_08_missing_release(self):self.case(lambda u,h:(u.__delitem__(slice(-2,None)),h.pop()),'incomplete','lifecycle_unclosed')
 def test_09_blank_activity_witness(self):
  u,h=trace(0);u[0]['blank']=True;h[1].update(sampling=26);h[2].update(sampling=27);g=pair.analyze(u,h);self.assertEqual(g['status'],'protocol_pass');self.assertTrue(g['blank_activity_received'])
 def test_10_script_confounded(self):self.case(lambda u,h:h[1].update(script_mask=33554432),'incomplete','script_confounded')
 def test_11_cap_reached(self):self.case(lambda u,h:h.append(dict(event='limit_reached',limit=1024)),'incomplete','limit_reached')
 def test_12_read_crosses_publish(self):self.case(lambda u,h:h[1].update(read_start_ns=215,time_ns=225),'incomplete','concurrent_undetermined')
 def test_13_stable_read_after_publish(self):self.case(lambda u,h:h[1].update(read_start_ns=230,time_ns=250),'protocol_pass')
 def test_14_duplicate_sampling(self):self.case(lambda u,h:h[1].update(sampling=1),'incomplete','sampling_not_forward')
 def test_15_fractional_integer(self):self.case(lambda u,h:h[1].update(lx=32767.9),'invalid_trace','bad_integer')
 def test_16_group_tail(self):self.case(lambda u,h:u[3].update(event_last_seq=1),'invalid_trace','event_group_not_closed')
 def test_17_no_dual_stream(self):
  u,h=trace();g=pair.analyze(u,None);self.assertEqual(g['status'],'pair_not_executed');self.assertFalse(g['physical_pass_claimed'])
 def test_18_state_mismatch(self):self.case(lambda u,h:h[1].update(lx=100),'incomplete','returned_state_mismatch')
 def test_19_device_domain_not_physical(self):
  u,h=trace();g=pair.analyze(u,h,domain='device');self.assertEqual(g['status'],'protocol_pass');self.assertFalse(g['physical_pass_claimed'])
 def test_20_slot_transition(self):self.case(lambda u,h:u[2].update(slot=1),'invalid_trace','slot_transition')
 def test_21_touch_timestamp_not_clock(self):
  u,h=trace();u[2]['touch_timestamp_s']=1e20;g=pair.analyze(u,h);self.assertEqual(g['status'],'protocol_pass')
 def test_22_release_not_neutral(self):
  def f(u,h):u[-1]['lx']=100;h[-1]['lx']=100
  self.case(f,'incomplete','release_not_neutral')
 def test_23_blank_unwanted_A(self):
  def f(u,h):u[0]['blank']=True;u[1]['buttons']=1;h[0]['buttons']=1
  self.case(f,'incomplete','blank_unwanted_A')
 def test_24_read_crosses_next_publish(self):self.case(lambda u,h:h[1].update(read_start_ns=250,time_ns=315),'incomplete','concurrent_undetermined')
 def test_25_unsigned_attribute_corruption(self):self.case(lambda u,h:h[1].update(attributes=-1),'invalid_trace','unsigned_range')
 def test_26_read_start_equals_publish_end(self):
  self.case(lambda u,h:h[1].update(read_start_ns=u[3]['publish_end_ns']),'incomplete','concurrent_undetermined')
 def test_27_matched_int32_overflow(self):
  def f(u,h):u[3]['lx']=2**31;h[1]['lx']=2**31
  self.case(f,'invalid_trace','int32_range')
 def binding_trace(self):
  u,h=trace();v=dict(buttons=256,lx=0,ly=0,rx=0,ry=0)
  u.insert(4,dict(stage='output',receiptseq=3,eventseq=2,event_first_seq=0,event_last_seq=2,mono_ns=260,publish_end_ns=270,source='bindings',phase='none',mode='game',**v))
  u[-1]['receiptseq']=4
  h.insert(2,dict(event='npad_return',read_start_ns=275,time_ns=280,sampling=3,id=32,style=2,attributes=1,script_mask=0,**v));h[-1]['sampling']=4
  return u,h
 def test_28_bindings_output_not_new_touch(self):
  u,h=self.binding_trace();g=pair.analyze(u,h)
  self.assertEqual(g['status'],'protocol_pass',g);self.assertEqual(g['touch_output_pairs'],3)
  self.assertEqual(g['pairs'][2]['attribution'],'output_only_not_new_touch')
  self.assertEqual(g['pairs'][2]['matched_sampling'],[3]);self.assertFalse(g['physical_pass_claimed'])
 def test_29_bindings_only_cannot_claim_touch(self):
  u,h=self.binding_trace();u=[u[4]];u[0].update(receiptseq=1,eventseq=0,event_first_seq=0,event_last_seq=0);h=[h[2]]
  g=pair.analyze(u,h);self.assertEqual(g['status'],'incomplete',g);self.assertIn('no_touch_pairs',g['reasons'])
 def test_30_bindings_cannot_be_touch_event(self):
  u,h=trace();u[0]['source']='bindings';g=pair.analyze(u,h)
  self.assertEqual(g['status'],'invalid_trace');self.assertIn('bad_event_source_phase',g['reasons'])
 def test_31_bindings_must_use_none_phase(self):
  u,h=self.binding_trace();u[4]['phase']='began';g=pair.analyze(u,h)
  self.assertEqual(g['status'],'invalid_trace');self.assertIn('bad_output_phase',g['reasons'])
 def test_32_unknown_program_source_still_rejected(self):
  u,h=self.binding_trace();u[4]['source']='unfrozen_future_source';g=pair.analyze(u,h)
  self.assertEqual(g['status'],'invalid_trace');self.assertIn('bad_source_or_mode',g['reasons'])
if __name__=='__main__':unittest.main()

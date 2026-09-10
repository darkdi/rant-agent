"""Bound tool history without dropping half of a call/result exchange."""
import copy,json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'local-assistant'))
from browser_review import historical_browser_result

def compact_turn(messages,base_count,browser=False,budget=48000):
 base=copy.deepcopy(messages[:base_count]);groups=[]
 for message in copy.deepcopy(messages[base_count:]):
  if message.get('role')!='tool' or not groups:groups.append([])
  groups[-1].append(message)
 if browser:
  page_messages=[]
  for group in groups:
   for m in group:
    if m.get('role')!='tool':continue
    try:data=json.loads(m.get('content',''))
    except (ValueError,TypeError):continue
    if isinstance(data,dict) and ('page' in data or 'controls' in data):page_messages.append((m,data))
  for m,data in page_messages[:-1]:
   data=historical_browser_result(data)
   m['content']=json.dumps(data,ensure_ascii=False)
 def size():
  # Encoded image bytes aren't language tokens; retain images while bounding text.
  def estimate(value):
   if isinstance(value,str):return 4000 if value.startswith('data:image/') else len(value)
   if isinstance(value,list):return sum(estimate(v) for v in value)
   if isinstance(value,dict):return sum(len(k)+estimate(v) for k,v in value.items())
   return len(str(value))
  return estimate(base+[m for g in groups for m in g])
 removed=[]
 while len(groups)>1 and (len(groups)>8 or size()>budget):
  group=groups.pop(0)
  for m in group:
   for c in m.get('tool_calls',[]):removed.append(c.get('function',{}).get('name','действие'))
 if removed:base.append({'role':'user','content':'Служебная сводка текущего задания: ранние вызовы '+', '.join(removed[-16:])+'. Их подробные снимки убраны. Это не подтверждение успеха; проверяй текущую страницу. Цель задания сохранена выше.'})
 return base+[m for g in groups for m in g]

"""Evidence-based continuation for browser tasks, shared by local/API loops."""
import re

HISTORY_MARKER='[Сохранённый отчёт IDE'
def clean_browser_text(text):
 return str(text).split(HISTORY_MARKER)[0].strip()

def clean_browser_history(history):
 return [{**m,'content':re.sub(r'(?:\(?ID\s*[:=]?\s*[\w-]+\)?)', '[устаревший ID удалён]', clean_browser_text(m.get('content','')), flags=re.I)} for m in history if m.get('role') in {'user','assistant'}]

def historical_browser_result(data):
 """Keep observed facts and tab identity while discarding stale interactive targets."""
 if not isinstance(data,dict):return data
 page=data.get('page',data)
 if not isinstance(page,dict) or not ('controls' in page or 'url' in page or 'text' in page):return data
 summary={k:page[k] for k in ('url','title','tab_id') if page.get(k)}
 summary['historical']=True
 summary['note']='Ранее проверенная страница: заголовок и вкладка сохранены. Старые ID удалены. Для текущих действий используй последний снимок; не повторяй переход ради уже известного заголовка.'
 if page.get('text'):summary['observed_excerpt']=str(page['text'])[:350]
 if 'page' in data:return {**{k:v for k,v in data.items() if k!='page'},'page_summary':summary}
 return summary

class BrowserReview:
 def __init__(self,task=''):
  self.records=[];self.retries=0
  self.needs_action=bool(re.search(r'отклик|нажми|кликни|заполни|отправь|введи|выбери',task,re.I)) and not bool(re.search(r'как |не (?:отправ|отклик|нажим)|ничего не',task,re.I))
 def observe(self,name,result):self.records.append((name,result))
 def review(self,text):
  text=clean_browser_text(text)
  if re.search(r'(?:не удалось (?:продолжить|завершить|выполнить)|(?:запись|отправка|бронирование|выполнение|отклик)[^.!?\n]{0,70}не подтвержден[аоы]?|не смог[^.!?\n]{0,50}(?:завершить|выполнить))',text,re.I):return {'final':text,'status':'incomplete'}
  successes=[(n,r) for n,r in self.records if isinstance(r,dict) and not r.get('error')]
  failed=bool(self.records and self.records[-1][1].get('error'))
  # Handing secret fields / CAPTCHA to the user is an actual tool pause, never an instruction with an ID.
  handoff=bool(re.search(r'\b(?:нажми(?:те)?|кликни(?:те)?|введи(?:те)?|заполни(?:те)?|выбери(?:те)?)\b.{0,160}(?:кноп|пол[ея]|ID\s*:|отклик|ссылк)',text,re.I|re.S))
  promise=bool(re.search(r'(?:сейчас\s+(?:я\s+)?(?:начну|буду|откликнусь|нажму|открою|посмотрю)|сначала\s+(?:я\s+)?(?:посмотрю|открою)|я\s+(?:начну|продолжу)\s+отклик)',text,re.I))
  unsupported=not any(n in {'browser_click','browser_type','browser_select'} for n,r in successes) and bool(re.search(r'(?:отклик(?:нулся|нулась|и\s+отправлены)|отправил(?:а)?|нажал(?:а)?|заполнил(?:а)?)',text,re.I))
  no_action=self.needs_action and not any(n in {'browser_click','browser_type','browser_select'} for n,r in successes) and '?' not in text
  if not successes or failed or handoff or promise or unsupported or no_action:
   if self.retries<2:
    self.retries+=1
    return {'retry':'Задача ещё не завершена. Не передавай пользователю обычный клик и не показывай ID в ответе. Выполни следующий шаг через browser_*; при выданном доступе обычные действия выполняются без повторного разрешения. Для ручного входа/кода/CAPTCHA вызови browser_wait_user. При ошибке обнови browser_snapshot или объясни конкретное препятствие без выдуманного успеха. Если задача уже выполнена, опиши только подтверждённый результат. Не копируй служебные отчёты.'}
   return {'final':'Агент не смог подтвердить выполнение задачи. '+('Последняя ошибка инструмента: '+str(self.records[-1][1]['error']) if failed else 'Модель остановилась на описании действий. Отправка или отклик не подтверждены.'),'status':'incomplete'}
  return {'final':text,'status':'model_finished'}

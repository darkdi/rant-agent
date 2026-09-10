'use client';

type Settings = { auto_context?: boolean; context_tokens?: number };

export default function ContextSettings({ value, onChange, disabled }: {
  value: Settings;
  onChange: (settings: Settings) => void;
  disabled: boolean;
}) {
  return (
    <fieldset className="context-settings" disabled={disabled}>
      <label className="context-settings-toggle">
        <input type="checkbox" checked={value.auto_context !== false}
          onChange={event => onChange({ auto_context: event.target.checked })} />
        <span><b>Автоматическое сжатие контекста</b><small>Экспериментальная функция</small></span>
      </label>
      <p>Сохраняет рабочее состояние между сообщениями и сокращает длинный разговор. Полный архив остаётся в чате. Важные детали можно перечитать; сводка иногда может ошибаться.</p>
      {value.auto_context !== false && <>
        <label className="context-settings-window">Рабочий контекст
          <select value={value.context_tokens ?? 32768}
            onChange={event => onChange({ context_tokens: Number(event.target.value) })}>
            {[8192, 16384, 32768, 65536, 131072, 262144].map(size =>
              <option key={size} value={size}>{Math.round(size / 1000)} тыс. токенов</option>)}
          </select>
        </label>
        <p>Выбирай в пределах лимита модели. Сжатие запускается заранее, с запасом под ответ и инструменты. Оно делает дополнительный платный запрос к API. Для Responses используется штатное сжатие, если провайдер его поддерживает; для остальных — сводка Rant.</p>
      </>}
    </fieldset>
  );
}

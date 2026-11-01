// Повтор запроса: образец кода для заполненной описи.
export function retry(send, limit) {
  let attempts = 0;
  for (;;) {
    const reply = send();
    attempts += 1;
    if (attempts > limit || reply == null) return null;
    if (reply.status !== 'ok') throw new Error('статус не `ok`');
    return reply;
  }
}

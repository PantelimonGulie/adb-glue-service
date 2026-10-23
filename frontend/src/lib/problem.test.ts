import { expect, it } from 'vitest';
import { plainProblem, seconds } from './problem';

it('turns HTTP codes and exception names into plain words', () => {
  expect(plainProblem('HTTP 503 after 5 attempts')).toBe('not available after 5 tries');
  expect(plainProblem('HTTP 429')).toBe('asked Glue to slow down');
  expect(plainProblem('HTTP 500')).toBe('a server error');
  expect(plainProblem('ReadTimeout: ')).toBe('no answer in time');
  expect(plainProblem('ConnectError: [Errno 111] Connection refused after 5 attempts')).toBe(
    'could not connect after 5 tries',
  );
  expect(plainProblem('warehouse cancel not delivered: HTTP 503 after 5 attempts')).toBe(
    'warehouse cancel not delivered: not available after 5 tries',
  );
});

it('says which message Glue could not handle, without the URL or the class name', () => {
  const raw =
    "unexpected while handling emag.notification: HTTPStatusError: Client error '404 Not Found' for url 'http://emag:8002/api-3/order/read'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404";

  expect(plainProblem(raw)).toBe('could not handle an eMAG message: not found');
});

it('leaves text that is already plain as it is', () => {
  expect(plainProblem('warehouse has no stock: sold on another channel first')).toBe(
    'warehouse has no stock: sold on another channel first',
  );
});

it('says how long Glue waits in whole words', () => {
  expect(seconds(0.56)).toBe('0.6 seconds');
  expect(seconds(1)).toBe('1 second');
  expect(seconds(2.04)).toBe('2 seconds');
});

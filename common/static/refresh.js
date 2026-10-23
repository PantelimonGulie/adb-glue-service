// Reloads the page every few seconds so it shows what Glue just did, unless someone is typing
// or has changed a field they have not sent yet.
const EVERY_MS = 4000;
const FIELDS = 'input:not([type="hidden"]), select, textarea';

function busy() {
  if (document.hidden || document.activeElement?.matches(FIELDS)) return true;
  return [...document.querySelectorAll(FIELDS)].some((field) => field.value !== field.defaultValue);
}

setInterval(() => {
  if (!busy()) location.reload();
}, EVERY_MS);

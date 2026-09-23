/* ==========================================================================
   api.js — the only place the storefront talks to the Python API.
   The API origin comes from <meta name="vrc-api">, written by build.py from
   site.api_base in data/products.json. Empty means same origin (/api/...).
   ========================================================================== */

const BASE = document.querySelector('meta[name="vrc-api"]')?.content?.replace(/\/$/, '') || '';

const FIELD_LABELS = {
  email: 'Email', name: 'Name', address1: 'Street address', city: 'City',
  state: 'State', postal_code: 'ZIP code', message: 'Message', topic: 'Topic',
  payment_method: 'Payment method', ruo_confirmed: 'Confirmation', items: 'Cart',
  reference: 'Order reference',
};

/** Turn any error body into one sentence a customer can act on.
 *  FastAPI validation errors arrive as an array of objects — rendering that
 *  directly is how you end up showing people "[object Object]". */
async function readError(res) {
  let data = {};
  try { data = await res.json(); } catch { /* non-JSON body */ }

  const detail = data.detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
    const raw = String(first.msg || '');
    if (field === 'email') return 'Enter a valid email address';
    // Our own validators already write full sentences; pydantic's built-ins
    // don't name the field, so prefix those with a readable label.
    if (raw.startsWith('Value error, ')) return raw.slice(13);
    return `${FIELD_LABELS[field] || 'A field'}: ${raw.charAt(0).toLowerCase()}${raw.slice(1)}`;
  }
  if (typeof detail === 'string') return detail;
  // Non-JSON 404/405/501: no API behind this host (e.g. the GitHub Pages preview).
  if (!('detail' in data) && [404, 405, 501].includes(res.status)) {
    return "This site isn't connected to its server yet";
  }
  if (res.status === 429) return 'Too many attempts in a short time. Wait a minute and try again';
  if (res.status >= 500) return 'The server hit an error';
  return `The request failed (${res.status})`;
}

export async function api(path, { method = 'GET', body, keepalive = false } = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      keepalive,
    });
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again");
  }
  if (!res.ok) throw new Error((await readError(res)).replace(/\.$/, ''));
  return res.status === 204 ? null : res.json();
}

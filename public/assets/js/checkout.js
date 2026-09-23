import * as cart from './store.js?v=3f42e75db9';
import{api}from './api.js?v=3f42e75db9';
import{esc,toast,ROOT}from './ui.js?v=3f42e75db9';
const $=(sel,root=document)=>root.querySelector(sel);
const LAST_ORDER='vrc.last-order.v1';
function lineRows(items){
return items.map((i)=>`
    <tr>
      <th scope="row">${esc(i.name)} <span class="muted">&times; ${i.qty}</span></th>
      <td style="text-align:right">${cart.money(i.line_total??i.price * i.qty)}</td>
    </tr>`).join('');
}
function totalRows(t,promo){
return `
    <tr><th scope="row">Subtotal</th><td style="text-align:right">${cart.money(t.subtotal)}</td></tr>
    ${t.discount>0?`<tr><th scope="row">Discount${promo?` (${esc(promo)})`:''}</th><td style="text-align:right">&minus;${cart.money(t.discount)}</td></tr>`:''}
    <tr><th scope="row">Shipping</th><td style="text-align:right">${t.shipping===0?'Free':cart.money(t.shipping)}</td></tr>
    <tr class="total"><th scope="row">Total</th><td style="text-align:right">${cart.money(t.total)}</td></tr>`;
}
async function renderSummary(box,submit){
const state=cart.getState();
if(!state.items.length){
box.innerHTML=`
      <div class="empty-state" style="padding:var(--s-6) 0">
        <p>Your cart is empty.</p>
        <a class="btn btn-copper" href="${ROOT}/shop/">Browse the catalog</a>
      </div>`;
if(submit)submit.disabled=true;
return;
}
if(submit)submit.disabled=false;
const draw=(items,totals,note)=>{
box.innerHTML=`
      <table class="sum-table">
        <tbody>${lineRows(items)}${totalRows(totals,state.promo)}</tbody>
      </table>
      ${note?`<p class="note" style="margin-top:var(--s-3)">${note}</p>`:''}`;
};
draw(state.items,cart.totals(),'Confirming prices with the server…');
try{
const priced=await api('/api/cart/price',{
method:'POST',
body:{
items:state.items.map((i)=>({sku:i.sku,qty:i.qty})),
promo_code:state.promo,
},
});
const notes=priced.notices?.length?priced.notices.map(esc).join(' '):'';
draw(priced.items,priced,notes||'Prices confirmed against the live catalog.');
}catch(err){
draw(state.items,cart.totals(),
`Showing an estimate: ${esc(err.message)}. Final figures are confirmed when you place the order.`);
}
}
function copyable(value){
return `<span class="mono">${esc(value)}</span>
    <button class="btn btn-ghost btn-sm" type="button" data-copy="${esc(value)}">Copy</button>`;
}
function renderConfirmation(main,order){
const pay=order.payment_instructions||{};
const rows=[];
if(pay.method)rows.push(['Method',esc(pay.method)]);
if(pay.handle)rows.push(['Send to',copyable(pay.handle)]);
if(pay.addresses){
Object.entries(pay.addresses).forEach(([coin,addr])=>rows.push([`${esc(coin)} address`,copyable(addr)]));
}
rows.push(['Amount',copyable(pay.amount||cart.money(order.total))]);
rows.push(['Payment note',copyable(order.reference)]);
main.innerHTML=`
    <span class="pill pill-green"><span class="dot"></span>Order placed</span>
    <h2 style="margin-top:var(--s-4)">Order <span class="mono">${esc(order.reference)}</span></h2>
    <p class="lead" style="margin-top:var(--s-3)">
      Send payment using the details below. Your order ships the next business
      day after payment clears.
    </p>
    <h3 style="margin-top:24px">How to pay</h3>
    <table class="sum-table pay-table">
      <tbody>${rows.map(([k,v])=>`<tr><th scope="row">${k}</th><td>${v}</td></tr>`).join('')}</tbody>
    </table>
    ${pay.note?`<p class="small" style="margin-top:var(--s-4)"><strong>${esc(pay.note)}</strong></p>`:''}
    <p class="small muted" style="margin-top:var(--s-4)">
      A copy of these instructions was sent to ${esc(order.email)}. You can check
      progress any time on the <a href="${ROOT}/order-status/">order status page</a>
      with your reference and email.
    </p>`;
main.onclick=async(e)=>{
const btn=e.target.closest('[data-copy]');
if(!btn)return;
try{
await navigator.clipboard.writeText(btn.dataset.copy);
toast('Copied');
}catch{
toast('Copy failed. Select the text and copy it manually.');
}
};
main.scrollIntoView({block:'start'});
}
export function initCheckout(){
const form=$('#checkout-form');
const main=$('#checkout-main');
const box=$('#checkout-summary');
if(!form||!main||!box)return;
const submit=$('button[type="submit"]',form);
const status=$('[data-status]',form);
try{
const saved=JSON.parse(sessionStorage.getItem(LAST_ORDER)||'null');
if(saved&&!cart.getState().items.length){
renderConfirmation(main,saved);
box.innerHTML='<p class="note">Order placed. Your cart is empty.</p>';
return;
}
}catch{}
renderSummary(box,submit);
let pending;
cart.subscribe(()=>{clearTimeout(pending);pending=setTimeout(()=>renderSummary(box,submit),250);});
form.addEventListener('submit',async(e)=>{
e.preventDefault();
if(!form.reportValidity())return;
const state=cart.getState();
if(!state.items.length){
status.textContent='Your cart is empty. Add a product before placing an order.';
status.className='err';
return;
}
const f=new FormData(form);
const payload={
email:f.get('email'),name:f.get('name'),
address1:f.get('address1'),address2:f.get('address2')||'',
city:f.get('city'),state:String(f.get('state')||'').toUpperCase(),
postal_code:f.get('postal_code'),
payment_method:f.get('payment_method'),
ruo_confirmed:f.get('ruo_confirmed')==='true',
website:f.get('website')||'',
items:state.items.map((i)=>({sku:i.sku,qty:i.qty})),
promo_code:state.promo,
};
submit.disabled=true;
submit.textContent='Placing order…';
status.textContent='';
try{
const order=await api('/api/orders',{method:'POST',body:payload});
try{sessionStorage.setItem(LAST_ORDER,JSON.stringify(order));}catch{}
cart.clear();
renderConfirmation(main,order);
box.innerHTML='<p class="note">Order placed. Your cart is empty.</p>';
}catch(err){
status.textContent=`${err.message}. Email support@vrcsolutions.co if this keeps happening.`;
status.className='err';
submit.disabled=false;
submit.textContent='Place order';
}
});
}
const STATUS_COPY={
awaiting_payment:['Awaiting payment','Send payment with your reference in the note. We confirm it and ship the next business day.'],
paid:['Payment confirmed','Your order is being prepared.'],
packed:['Packed','Packed and waiting for carrier pickup.'],
shipped:['Shipped','On its way.'],
delivered:['Delivered','The carrier reports this order as delivered.'],
cancelled:['Cancelled','This order was cancelled.'],
refunded:['Refunded','This order was refunded.'],
};
export function initOrderStatus(){
const form=$('#status-form');
const out=$('#status-result');
if(!form||!out)return;
const status=$('[data-status]',form);
const submit=$('button[type="submit"]',form);
form.addEventListener('submit',async(e)=>{
e.preventDefault();
if(!form.reportValidity())return;
const ref=String(new FormData(form).get('reference')).trim().toUpperCase();
const email=String(new FormData(form).get('email')).trim();
submit.disabled=true;
status.textContent='';
out.innerHTML='';
try{
const o=await api(`/api/orders/${encodeURIComponent(ref)}?email=${encodeURIComponent(email)}`);
const[label,desc]=STATUS_COPY[o.status]||[o.status,''];
out.innerHTML=`
        <span class="pill ${o.status==='cancelled'?'pill-amber':'pill-green'}"><span class="dot"></span>${esc(label)}</span>
        <h2 style="margin-top:var(--s-3)">Order <span class="mono">${esc(o.reference)}</span></h2>
        <p class="small muted" style="margin-top:var(--s-2)">${esc(desc)}</p>
        <table class="sum-table" style="margin-top:16px">
          <tbody>
            ${o.tracking_number?`<tr><th scope="row">Tracking</th><td class="mono">${esc(o.tracking_number)}</td></tr>`:''}
            <tr><th scope="row">Total</th><td>${cart.money(o.total)}</td></tr>
            ${o.items.map((i)=>`
              <tr><th scope="row">${esc(i.name)} &times; ${i.qty}</th>
                <td>${i.lot&&!i.lot.startsWith('PLACEHOLDER')
?`Lot <a class="mono" href="${ROOT}/coa-library/?q=${encodeURIComponent(i.lot)}">${esc(i.lot)}</a>`
:'<span class="muted">Lot on vial label</span>'}</td></tr>`).join('')}
          </tbody>
        </table>
        <p class="note" style="margin-top:var(--s-3)">Each lot links to its certificate, so you can check what you received.</p>`;
}catch(err){
status.textContent=`${err.message}.`;
status.className='err';
}finally{
submit.disabled=false;
}
});
}

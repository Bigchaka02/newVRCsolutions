import{
initNav,initHeader,initCart,initGate,initCatalog,
initLedger,initForms,initPromo,
}from './ui.js?v=3f42e75db9';
import{initCheckout,initOrderStatus}from './checkout.js?v=3f42e75db9';
import{initFx}from './fx.js?v=3f42e75db9';
function boot(){
initNav();
initHeader();
initCart();
initGate();
initCatalog();
initLedger();
initForms();
initPromo();
initCheckout();
initOrderStatus();
try{initFx();}catch(err){console.error('[fx]',err);}
}
if(document.readyState==='loading'){
document.addEventListener('DOMContentLoaded',boot,{once:true});
}else{
boot();
}

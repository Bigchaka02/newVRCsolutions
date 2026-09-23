import{
initNav,initHeader,initCart,initGate,initCatalog,
initLedger,initForms,initPromo,
}from './ui.js?v=69971ed99c';
import{initCheckout,initOrderStatus}from './checkout.js?v=69971ed99c';
import{initFx}from './fx.js?v=69971ed99c';
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

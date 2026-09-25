import{
initNav,initHeader,initCart,initGate,initCatalog,
initLedger,initForms,initPromo,
}from './ui.js?v=55d0e9b26f';
import{initCheckout,initOrderStatus}from './checkout.js?v=55d0e9b26f';
import{initFx}from './fx.js?v=55d0e9b26f';
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

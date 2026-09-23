import{
initNav,initHeader,initCart,initGate,initCatalog,
initLedger,initForms,initPromo,
}from './ui.js?v=d01efa99ea';
import{initCheckout,initOrderStatus}from './checkout.js?v=d01efa99ea';
import{initFx}from './fx.js?v=d01efa99ea';
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

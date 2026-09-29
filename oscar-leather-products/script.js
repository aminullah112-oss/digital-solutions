const WHATSAPP_NUMBER="917904927682";
const quoteText="Hello Oscar Leather Products, I found your website. I would like a quote for custom leather keychains. Please share pricing, minimum quantity and lead time.";
const wa=`https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(quoteText)}`;
["heroWa","quoteWa","contactWa"].forEach(id=>{const el=document.getElementById(id);if(el)el.href=wa});
document.getElementById("year").textContent=new Date().getFullYear();

const io=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add("visible")}),{threshold:.12});
document.querySelectorAll(".reveal,.section").forEach(x=>io.observe(x));

window.addEventListener("scroll",()=>{
 const h=document.documentElement.scrollHeight-innerHeight;
 document.querySelector(".progress").style.width=(scrollY/h*100)+"%";
 document.querySelector(".nav").style.background=scrollY>40?"rgba(17,11,7,.88)":"transparent";
 document.querySelector(".nav").style.backdropFilter=scrollY>40?"blur(14px)":"none";
},{passive:true});

document.querySelector(".menu")?.addEventListener("click",()=>{
 const nav=document.querySelector(".nav nav");
 nav.style.display=nav.style.display==="flex"?"none":"flex";
 nav.style.position="absolute";nav.style.top="75px";nav.style.left="5vw";nav.style.right="5vw";
 nav.style.padding="20px";nav.style.flexDirection="column";nav.style.background="rgba(20,13,9,.96)";
});

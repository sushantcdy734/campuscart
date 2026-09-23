let products=[],cart=JSON.parse(localStorage.getItem('campusCart')||'[]'),activeCategory='All',currentUser=null;
const money=n=>'Rs. '+Number(n).toLocaleString('en-IN');
async function api(url,options={}){const r=await fetch(url,{...options,headers:{...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(options.headers||{})}});let d={};try{d=await r.json()}catch{};if(!r.ok)throw Error(d.error||'Something went wrong');return d}
async function loadProducts(){try{products=(await api('/api/products')).products;renderProducts()}catch(e){showToast(e.message)}}
function imageHtml(p,cls='product-img'){return p.image_url?`<img class="${cls}" src="${p.image_url}" alt="${escapeHtml(p.name)}">`:`<div class="${cls} emoji-img">${p.icon||'📦'}</div>`}
function escapeHtml(s=''){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function renderProducts(){
  const q=(document.getElementById('searchInput')?.value||'').trim().toLowerCase();
  const max=Number(document.getElementById('maxPrice')?.value||0);
  const minRating=Number(document.getElementById('minRating')?.value||0);
  const inStock=Boolean(document.getElementById('inStockOnly')?.checked);
  let arr=products.filter(p=>{
    const hay=(p.name+' '+p.category+' '+(p.description||'')+' '+(p.seller_name||'')).toLowerCase();
    return (activeCategory==='All'||p.category===activeCategory)&&(!q||hay.includes(q))&&(!max||Number(p.price)<=max)&&(!inStock||Number(p.stock)>0)&&(!minRating||Number(p.rating||0)>=minRating);
  });
  const sort=document.getElementById('sortSelect')?.value;
  if(sort==='low')arr.sort((a,b)=>Number(a.price)-Number(b.price));
  if(sort==='high')arr.sort((a,b)=>Number(b.price)-Number(a.price));
  const grid=document.getElementById('productGrid');
  grid.innerHTML=arr.length?arr.map(p=>`<article class="product" data-product-id="${p.id}">${imageHtml(p)}<div class="product-body"><span class="tag">${escapeHtml(p.category)}</span><h3>${escapeHtml(p.name)}</h3><p>${escapeHtml(p.description||'')}</p><small class="seller-line">Seller: ${escapeHtml(p.seller_name||'CampusCart')} · Stock ${p.stock}</small><div class="product-actions">${p.seller_id?`<button class="link-btn" onclick="openStore(${p.seller_id})">Visit store</button>${currentUser&&Number(currentUser.id)===Number(p.seller_id)?'<span class="seller-line">Your listing</span>':`<button class="secondary chat-seller" onclick="openChat(${p.seller_id},${p.id})">💬 Chat seller</button>`}`:''}</div><div class="price-row"><span class="price">${money(p.price)}</span><button class="add" onclick="addToCart(${p.id})">+ Add</button></div></div></article>`).join(''):`<div class="empty" style="grid-column:1/-1">No products found.</div>`;
}
function filterCategory(c){activeCategory=c;document.getElementById('products').scrollIntoView({behavior:'smooth'});renderProducts()}
function addToCart(id){const p=products.find(x=>x.id===id);if(!p)return;const item=cart.find(x=>x.id===id);if(item){if(item.qty>=p.stock)return showToast('Maximum available stock reached');item.qty++}else cart.push({...p,qty:1});saveCart();showToast('Added to cart')}
function saveCart(){localStorage.setItem('campusCart',JSON.stringify(cart));updateCart();renderCart()}
function updateCart(){document.getElementById('cartCount').textContent=cart.reduce((s,x)=>s+x.qty,0)}
function renderCart(){const el=document.getElementById('cartItems');if(!cart.length){el.innerHTML='<div class="empty">🛒<br><br>Your cart is empty.</div>';document.getElementById('cartTotal').textContent=money(0);return}el.innerHTML=cart.map(x=>`<div class="cart-item">${imageHtml(x,'cart-icon')}<div style="flex:1"><h4>${escapeHtml(x.name)}</h4><small>${money(x.price)} × ${x.qty}</small></div><button class="add" onclick="removeOne(${x.id})">−</button></div>`).join('');document.getElementById('cartTotal').textContent=money(cart.reduce((s,x)=>s+x.price*x.qty,0))}
function removeOne(id){let x=cart.find(a=>a.id===id);if(x.qty>1)x.qty--;else cart=cart.filter(a=>a.id!==id);saveCart()}
function openCart(){document.getElementById('cartPanel').classList.add('open');document.getElementById('overlay').classList.add('open');renderCart()}
function closeCart(){document.getElementById('cartPanel').classList.remove('open');document.getElementById('overlay').classList.remove('open')}
async function checkout(){if(!cart.length)return showToast('Your cart is empty');if(!currentUser)return openAuth('login');if(currentUser.role!=='buyer')return showToast('Only buyers can place orders');openCheckout()}
function openCheckout(){document.getElementById('checkoutContent').innerHTML=`<h2>Secure checkout</h2><p class="auth-sub">Payments are verified server-to-server before an order is marked paid.</p><div class="payment-grid"><button onclick="placeOrder('eSewa')">💚<b>eSewa</b><small>Secure gateway</small></button><button onclick="placeOrder('Khalti')">💜<b>Khalti</b><small>Secure gateway</small></button><button onclick="placeOrder('COD')">📦<b>Cash on Delivery</b><small>Pay when received</small></button></div><div class="checkout-total">Total: <b>${money(cart.reduce((s,x)=>s+x.price*x.qty,0))}</b></div>`;document.getElementById('checkoutOverlay').classList.add('open')}
function closeCheckout(){document.getElementById('checkoutOverlay').classList.remove('open')}
async function placeOrder(method){try{const d=await api('/api/checkout',{method:'POST',body:JSON.stringify({payment_method:method,items:cart.map(x=>({id:x.id,qty:x.qty}))})});if(d.payment==='redirect'&&d.provider==='Khalti'){window.location.href=d.payment_url;return}if(d.payment==='redirect'&&d.provider==='eSewa'){const form=document.createElement('form');form.method='POST';form.action=d.action;Object.entries(d.fields).forEach(([k,v])=>{const input=document.createElement('input');input.type='hidden';input.name=k;input.value=v;form.appendChild(input)});document.body.appendChild(form);form.submit();return}cart=[];saveCart();closeCheckout();closeCart();showToast(`Order #${d.order_id} placed`);loadProducts();openBuyerDashboard()}catch(e){showToast(e.message)}}
function openAuth(mode){const box=document.getElementById('authContent');box.innerHTML=mode==='login'?`<h2>Welcome back 👋</h2><p class="auth-sub">Login as a CampusCart buyer or seller.</p><form class="auth-form" onsubmit="loginUser(event)"><label>Email</label><input id="loginEmail" type="email" required placeholder="you@example.com"><label>Password</label><input id="loginPassword" type="password" required><button class="primary" type="submit">Login</button></form><div class="auth-switch">New here? <button onclick="openAuth('register')">Create an account</button></div>`:`<h2>Create your account</h2><p class="auth-sub">Choose how you will use CampusCart.</p><form class="auth-form" onsubmit="registerUser(event)"><label>Full name</label><input id="regName" required placeholder="Your name"><label>Email</label><input id="regEmail" type="email" required placeholder="you@example.com"><label>Password</label><input id="regPassword" type="password" minlength="6" required placeholder="At least 6 characters"><label>Account type</label><div class="role-grid"><button type="button" class="role-option active" id="buyerRole" onclick="selectRole('buyer')">🛒 Buyer</button><button type="button" class="role-option" id="sellerRole" onclick="selectRole('seller')">🏪 Seller</button></div><input type="hidden" id="regRole" value="buyer"><button class="primary" type="submit">Create account</button></form><div class="auth-switch">Already registered? <button onclick="openAuth('login')">Login</button></div>`;document.getElementById('authOverlay').classList.add('open')}
function selectRole(role){document.getElementById('regRole').value=role;document.getElementById('buyerRole').classList.toggle('active',role==='buyer');document.getElementById('sellerRole').classList.toggle('active',role==='seller')}
function closeAuth(){document.getElementById('authOverlay').classList.remove('open')}
async function registerUser(e){e.preventDefault();try{await api('/api/register',{method:'POST',body:JSON.stringify({name:regName.value,email:regEmail.value,password:regPassword.value,role:regRole.value})});closeAuth();await loadUser();showToast('Account created successfully')}catch(err){showToast(err.message)}}
async function loginUser(e){e.preventDefault();try{await api('/api/login',{method:'POST',body:JSON.stringify({email:loginEmail.value,password:loginPassword.value})});closeAuth();await loadUser();showToast('Login successful')}catch(err){showToast(err.message)}}
async function loadUser(){try{const d=await api('/api/me');currentUser=d.user}catch(e){currentUser=null}const area=document.getElementById('userArea');if(currentUser){area.innerHTML=`<span class="user-chip">${currentUser.role==='seller'?'🏪':'🛒'} ${escapeHtml(currentUser.name)}</span><button class="link-btn" onclick="openDashboard()">Dashboard</button><button class="link-btn messages-nav" onclick="openMessageInbox()">💬 Messages</button><button class="link-btn" onclick="logoutUser()">Logout</button>`}else area.innerHTML=''}
async function logoutUser(){await api('/api/logout',{method:'POST'});currentUser=null;showToast('Logged out');loadUser()}
function openDashboard(){if(!currentUser)return openAuth('login');currentUser.role==='seller'?openSellerDashboard():openBuyerDashboard()}
async function openSellerDashboard(){try{const d=await api('/api/seller/products');const orders=await api('/api/orders');const totalSales=orders.orders.filter(o=>o.payment_status==='Paid'||o.payment_method==='COD').reduce((s,o)=>s+Number(o.total),0);document.getElementById('dashboardContent').innerHTML=`<div class="dashboard-header"><div><h2>Seller Dashboard 🏪</h2><p class="auth-sub">Manage listings, stock and customer orders.</p></div><button class="primary" onclick="showAddProduct()">+ Add product</button></div><div class="stats-grid"><div><b>${d.products.length}</b><small>Listings</small></div><div><b>${orders.orders.length}</b><small>Orders</small></div><div><b>${money(totalSales)}</b><small>Order value</small></div></div><h3 class="dash-title">My products</h3><div class="dash-list">${d.products.length?d.products.map(p=>`<div class="dash-row product-dash-row">${imageHtml(p,'dash-image')}<span><b>${escapeHtml(p.name)}</b><small>${money(p.price)} · Stock ${p.stock} · ${escapeHtml(p.category)}</small></span><button class="danger" onclick="deleteProduct(${p.id})">Delete</button></div>`).join(''):'<div class="empty">No products yet.</div>'}</div><h3 class="dash-title">Order management</h3><div class="dash-list">${orders.orders.length?orders.orders.map(o=>`<div class="dash-row"><span><b>Order #${o.id}</b><small>${escapeHtml(o.buyer_name)} · ${money(o.total)} · ${o.payment_method} · Payment: ${o.payment_status}</small></span><select onchange="updateOrderStatus(${o.id},this.value)">${['Pending','Confirmed','Ready','Delivered','Cancelled'].map(s=>`<option ${s===o.status?'selected':''}>${s}</option>`).join('')}</select></div>`).join(''):'<div class="empty">No orders yet.</div>'}</div>`;document.getElementById('dashboardOverlay').classList.add('open')}catch(e){showToast(e.message)}}
async function openBuyerDashboard(){if(!currentUser)return openAuth('login');try{const d=await api('/api/orders');const paid=d.orders.filter(o=>o.payment_status==='Paid'||o.payment_method==='COD').length;document.getElementById('dashboardContent').innerHTML=`<div class="dashboard-header"><div><h2>Buyer Dashboard 🛍️</h2><p class="auth-sub">Welcome, ${escapeHtml(currentUser.name)}. Track purchases and payments.</p></div><button class="secondary" onclick="openCart()">Open cart (${cart.reduce((s,x)=>s+x.qty,0)})</button></div><div class="stats-grid"><div><b>${d.orders.length}</b><small>Total orders</small></div><div><b>${paid}</b><small>Paid orders</small></div><div><b>${money(d.orders.reduce((s,o)=>s+Number(o.total),0))}</b><small>Total spend</small></div></div><h3 class="dash-title">My orders</h3>${d.orders.length?d.orders.map(o=>orderCard(o)).join(''):'<div class="empty">You have no orders yet. <button class="primary" onclick="closeDashboard();document.getElementById(\'products\').scrollIntoView()">Shop now</button></div>'}`;document.getElementById('dashboardOverlay').classList.add('open')}catch(e){showToast(e.message)}}
function orderCard(o){return `<div class="order-card"><div><b>Order #${o.id}</b><span class="status">${escapeHtml(o.status)}</span></div><small>${new Date(o.created_at).toLocaleString()} · ${escapeHtml(o.payment_method)} · Payment: ${escapeHtml(o.payment_status)} · <b>${money(o.total)}</b></small>${o.items?`<div class="order-items">${o.items.map(i=>`${i.icon||'📦'} ${escapeHtml(i.name)} × ${i.quantity}`).join('<br>')}</div>`:''}</div>`}
function closeDashboard(){document.getElementById('dashboardOverlay').classList.remove('open')}
function showAddProduct(){document.getElementById('dashboardContent').innerHTML=`<h2>Add a product</h2><p class="auth-sub">Upload a real product photo and publish your listing.</p><form class="auth-form" onsubmit="addProduct(event)"><label>Product name</label><input id="pName" required><label>Category</label><select id="pCategory"><option>Books</option><option>Electronics</option><option>Notes</option><option>Furniture</option><option>Clothing</option><option>Others</option></select><label>Price (Rs.)</label><input id="pPrice" type="number" min="1" step="0.01" required><label>Stock</label><input id="pStock" type="number" min="1" value="1" required><label>Product image</label><input id="pImage" type="file" accept="image/png,image/jpeg,image/webp,image/gif"><small class="field-help">Maximum 8 MB. JPG, PNG, WEBP or GIF.</small><label>Emoji fallback</label><input id="pIcon" value="📦"><label>Description</label><textarea id="pDesc" rows="3" placeholder="Condition, details, pickup..."></textarea><button class="primary">Publish product</button><button type="button" class="secondary" onclick="openSellerDashboard()">Back</button></form>`}
async function addProduct(e){e.preventDefault();try{const fd=new FormData();fd.append('name',pName.value);fd.append('category',pCategory.value);fd.append('price',pPrice.value);fd.append('stock',pStock.value);fd.append('icon',pIcon.value||'📦');fd.append('description',pDesc.value);if(pImage.files[0])fd.append('image',pImage.files[0]);await api('/api/products',{method:'POST',body:fd});showToast('Product published');await loadProducts();openSellerDashboard()}catch(err){showToast(err.message)}}
async function deleteProduct(id){if(!confirm('Delete this product?'))return;try{await api('/api/products/'+id,{method:'DELETE'});showToast('Product deleted');await loadProducts();openSellerDashboard()}catch(e){showToast(e.message)}}
async function updateOrderStatus(id,status){try{await api('/api/orders/'+id+'/status',{method:'PATCH',body:JSON.stringify({status})});showToast('Order status updated');openSellerDashboard()}catch(e){showToast(e.message)}}
async function openOrders(){return currentUser?.role==='buyer'?openBuyerDashboard():openSellerDashboard()}
function closeOrders(){closeDashboard()}
function handlePaymentReturn(){const p=new URLSearchParams(location.search).get('payment');const oid=new URLSearchParams(location.search).get('order');if(p==='success'){cart=[];saveCart();showToast(`Payment successful${oid?' — Order #'+oid:''}`);history.replaceState({},'',location.pathname);setTimeout(()=>{if(currentUser)openBuyerDashboard()},300)}else if(p==='failed'){showToast('Payment was not completed. Your order was cancelled.');history.replaceState({},'',location.pathname)}}
let toastTimer;function showToast(t){const x=document.getElementById('toast');x.textContent=t;x.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>x.classList.remove('show'),3000)}
document.getElementById('searchInput').addEventListener('input',renderProducts);document.getElementById('sortSelect').addEventListener('change',renderProducts);loadProducts();updateCart();renderCart();loadUser().then(handlePaymentReturn);

// ===== Pro upgrade UI =====
let wishlistIds=new Set();
async function loadWishlist(){if(!currentUser)return wishlistIds.clear();try{wishlistIds=new Set((await api('/api/wishlist')).products.map(p=>p.id))}catch(e){wishlistIds.clear()}}
async function toggleWishlist(id){if(!currentUser)return openAuth('login');try{let d=await api('/api/wishlist/'+id,{method:'POST'});d.saved?wishlistIds.add(id):wishlistIds.delete(id);renderProducts();showToast(d.saved?'Saved to wishlist ❤️':'Removed from wishlist')}catch(e){showToast(e.message)}}
const oldRenderProducts=renderProducts;renderProducts=function(){const q=(searchInput?.value||'').toLowerCase();let arr=products.filter(p=>(activeCategory==='All'||p.category===activeCategory)&&(p.name+' '+p.category+' '+(p.description||'')).toLowerCase().includes(q));const sort=sortSelect.value;if(sort==='low')arr.sort((a,b)=>a.price-b.price);if(sort==='high')arr.sort((a,b)=>b.price-a.price);productGrid.innerHTML=arr.length?arr.map(p=>`<article class="product">${imageHtml(p)}<button class="wish" onclick="toggleWishlist(${p.id})">${wishlistIds.has(p.id)?'♥':'♡'}</button><div class="product-body"><span class="tag">${escapeHtml(p.category)}</span><h3>${escapeHtml(p.name)}</h3><p>${escapeHtml(p.description||'')}</p><small class="seller-line">Seller: ${escapeHtml(p.seller_name||'CampusCart')} · Stock ${p.stock}</small><div class="price-row"><span class="price">${money(p.price)}</span><button class="add" onclick="addToCart(${p.id})">+ Add</button></div><button class="review-link" onclick="openReviews(${p.id})">⭐ Reviews</button></div></article>`).join(''):`<div class="empty" style="grid-column:1/-1">No products found.</div>`}
async function openReviews(id){try{const p=products.find(x=>x.id===id),d=await api('/api/products/'+id+'/reviews');dashboardContent.innerHTML=`<h2>⭐ ${escapeHtml(p.name)}</h2><p class="auth-sub">Average ${d.average}/5 from ${d.count} review(s)</p>${currentUser?.role==='buyer'?`<form class="auth-form" onsubmit="saveReview(event,${id})"><select id="reviewRating"><option value="5">★★★★★ Excellent</option><option value="4">★★★★ Good</option><option value="3">★★★ Okay</option><option value="2">★★ Poor</option><option value="1">★ Bad</option></select><textarea id="reviewComment" placeholder="Share your experience"></textarea><button class="primary">Save review</button></form>`:''}<div class="dash-list">${d.reviews.map(r=>`<div class="dash-row"><span><b>${escapeHtml(r.name)} · ${'★'.repeat(r.rating)}</b><small>${escapeHtml(r.comment||'No comment')}</small></span></div>`).join('')||'<div class="empty">No reviews yet.</div>'}</div>`;dashboardOverlay.classList.add('open')}catch(e){showToast(e.message)}}
async function saveReview(e,id){e.preventDefault();try{await api('/api/products/'+id+'/reviews',{method:'POST',body:JSON.stringify({rating:reviewRating.value,comment:reviewComment.value})});showToast('Review saved');openReviews(id)}catch(e){showToast(e.message)}}
async function openWishlist(){try{const d=await api('/api/wishlist');products=d.products;activeCategory='All';closeDashboard();document.getElementById('products').scrollIntoView({behavior:'smooth'});renderProducts();showToast('Showing your wishlist')}catch(e){showToast(e.message)}}
async function editProfile(){if(!currentUser)return;dashboardContent.innerHTML=`<h2>My profile 👤</h2><form class="auth-form" onsubmit="saveProfile(event)"><label>Name</label><input id="profileName" value="${escapeHtml(currentUser.name)}"><label>Email</label><input value="${escapeHtml(currentUser.email)}" disabled><button class="primary">Save changes</button></form>`;dashboardOverlay.classList.add('open')}
async function saveProfile(e){e.preventDefault();try{await api('/api/profile',{method:'PATCH',body:JSON.stringify({name:profileName.value})});await loadUser();showToast('Profile updated');closeDashboard()}catch(e){showToast(e.message)}}
function toggleDark(){document.body.classList.toggle('dark');localStorage.setItem('campusDark',document.body.classList.contains('dark'))}
if(localStorage.getItem('campusDark')==='true')document.body.classList.add('dark');
const oldLoadUser=loadUser;loadUser=async function(){await oldLoadUser();if(currentUser){await loadWishlist();userArea.innerHTML+=`<button class="link-btn" onclick="openWishlist()">♡ Wishlist</button><button class="link-btn" onclick="editProfile()">Profile</button>`}renderProducts()}
document.querySelector('.nav-actions').insertAdjacentHTML('beforeend','<button class="link-btn" onclick="toggleDark()">🌙</button>');
const oldSeller=openSellerDashboard;openSellerDashboard=async function(){try{const a=await api('/api/seller/analytics');await oldSeller();setTimeout(()=>{const s=document.querySelector('#dashboardContent .stats-grid');if(s)s.insertAdjacentHTML('beforeend',`<div><b>${a.units}</b><small>Units sold</small></div><div><b>${money(a.revenue)}</b><small>Revenue</small></div>`)},0)}catch(e){await oldSeller()}}
// ===== Ultimate Upgrade UI =====
async function applyCoupon(){const code=prompt('Enter coupon code (try CAMPUS10)');if(!code)return;try{const total=cart.reduce((s,x)=>s+x.price*x.qty,0),d=await api('/api/coupons/validate',{method:'POST',body:JSON.stringify({code,total})});showToast(`${d.code} applied! You save ${money(d.discount)}. New total ${money(d.total)}`)}catch(e){showToast(e.message)}}
const ultimateRender=renderProducts;renderProducts=function(){ultimateRender();document.querySelectorAll('.product').forEach((card,i)=>{const p=products.filter(x=>(activeCategory==='All'||x.category===activeCategory)&&((x.name+' '+x.category+' '+(x.description||'')).toLowerCase().includes((searchInput?.value||'').toLowerCase())))[i];if(p&&p.seller_id)card.querySelector('.product-body')?.insertAdjacentHTML('beforeend',`<button class="review-link" onclick="openChat(${p.seller_id},${p.id})">💬 Chat seller</button><button class="review-link" onclick="reportProduct(${p.id})">🚩 Report</button>`)} )}
async function reportProduct(id){if(!currentUser)return openAuth('login');const reason=prompt('Why are you reporting this listing?');if(!reason)return;try{await api('/api/reports',{method:'POST',body:JSON.stringify({product_id:id,reason})});showToast('Report submitted')}catch(e){showToast(e.message)}}
const oldOpenCheckout=openCheckout;openCheckout=function(){oldOpenCheckout();checkoutContent.insertAdjacentHTML('beforeend','<button class="secondary" onclick="applyCoupon()">🎟️ Apply coupon</button>')}
async function ultimateChat(id,pid){if(!currentUser)return openAuth('login');let msg=prompt('Message to seller:');if(!msg)return;try{await api('/api/messages',{method:'POST',body:JSON.stringify({receiver_id:id,product_id:pid,body:msg})});showToast('Message sent 💬')}catch(e){showToast(e.message)}}
async function ultimateCoupon(){let code=prompt('Coupon code (try CAMPUS10):');if(!code)return;try{let d=await api('/api/coupons/validate',{method:'POST',body:JSON.stringify({code,total:cart.reduce((s,x)=>s+x.price*x.qty,0)})});showToast(`Coupon applied! Save ${money(d.discount)} · New total ${money(d.total)}`)}catch(e){showToast(e.message)}}


// ===== Daraz-style Phase 3 UI =====
function toggleFilters(){filterPanel.classList.toggle('open')}
async function openAddresses(){if(!currentUser)return openAuth('login');try{let d=await api('/api/addresses');dashboardContent.innerHTML=`<h2>📍 Delivery addresses</h2><form class="auth-form" onsubmit="saveAddress(event)"><input id="addrLabel" placeholder="Home / Hostel" required><textarea id="addrFull" placeholder="Complete address" required></textarea><input id="addrPhone" placeholder="Phone number"><input id="addrCity" placeholder="City"><button class="primary">Save address</button></form><div class="dash-list">${d.addresses.map(a=>`<div class="dash-row"><span><b>${escapeHtml(a.label)}</b><small>${escapeHtml(a.full_address)} · ${escapeHtml(a.city||'')}</small></span></div>`).join('')||'<div class="empty">No saved addresses.</div>'}</div>`;dashboardOverlay.classList.add('open')}catch(e){showToast(e.message)}}
async function saveAddress(e){e.preventDefault();try{await api('/api/addresses',{method:'POST',body:JSON.stringify({label:addrLabel.value,full_address:addrFull.value,phone:addrPhone.value,city:addrCity.value})});showToast('Address saved');openAddresses()}catch(e){showToast(e.message)}}
async function openStoreSetup(){if(!currentUser)return openAuth('login');if(currentUser.role!=='seller')return showToast('Seller account required');dashboardContent.innerHTML=`<h2>🏪 Store settings</h2><form class="auth-form" onsubmit="saveStore(event)"><input id="storeName" placeholder="Store name" required><textarea id="storeDesc" placeholder="Tell buyers about your store"></textarea><button class="primary">Save store</button></form>`;dashboardOverlay.classList.add('open')}
async function saveStore(e){e.preventDefault();try{await api('/api/store',{method:'POST',body:JSON.stringify({store_name:storeName.value,description:storeDesc.value})});showToast('Store saved')}catch(e){showToast(e.message)}}
async function openStore(sid){try{let d=await api('/api/stores/'+sid);dashboardContent.innerHTML=`<h2>🏪 ${escapeHtml(d.store.store_name)}</h2><p>${escapeHtml(d.store.description||'')}</p><h3>Products</h3><div class="dash-list">${d.products.map(p=>`<div class="dash-row"><span><b>${escapeHtml(p.name)}</b><small>${money(p.price)} · Stock ${p.stock}</small></span><button class="add" onclick="addToCart(${p.id})">Add</button></div>`).join('')||'No products yet.'}</div>`;dashboardOverlay.classList.add('open')}catch(e){showToast(e.message)}}


// ===== Reliable messaging system =====
let chatContacts={};
function chatTime(v){if(!v)return '';const d=new Date(v);return isNaN(d)?String(v):d.toLocaleString()}
function chatContactName(id,fallback='Conversation'){return chatContacts[id]||products.find(p=>Number(p.seller_id)===Number(id))?.seller_name||fallback}

async function openMessageInbox(){
  if(!currentUser)return openAuth('login');
  try{
    const d=await api('/api/messages/conversations');
    chatContacts={};d.conversations.forEach(c=>chatContacts[c.user.id]=c.user.name);
    const list=d.conversations.length?d.conversations.map(c=>`<button class="dash-row chat-conversation" onclick="openChat(${Number(c.user.id)})"><span><b>${c.user.role==='seller'?'🏪':'🛒'} ${escapeHtml(c.user.name)} ${c.unread?`<em class="unread-badge">${c.unread}</em>`:''}</b><small>${escapeHtml(c.last.body)} · ${chatTime(c.last.created_at)}</small></span><span>Open ›</span></button>`).join(''):`<div class="empty chat-empty"><div class="empty-icon">💬</div><b>No conversations yet</b><p>Start by chatting with a seller or buyer.</p><button class="primary" onclick="openNewChat()">Start a new chat</button></div>`;
    dashboardContent.innerHTML=`<div class="dashboard-header"><div><h2>💬 Messages</h2><p class="auth-sub">Chat with buyers and sellers.</p></div><div class="message-actions"><button class="secondary" onclick="openNewChat()">＋ New chat</button><button class="secondary" onclick="closeDashboard()">Close</button></div></div><div class="dash-list">${list}</div>`;
    dashboardOverlay.classList.add('open');
  }catch(e){showToast(e.message)}
}

async function openNewChat(){
  if(!currentUser)return openAuth('login');
  try{
    const d=await api('/api/messages/contacts');
    const contacts=d.contacts||[];
    dashboardContent.innerHTML=`<div class="dashboard-header"><div><h2>💬 Start a new chat</h2><p class="auth-sub">Choose someone from the CampusCart marketplace.</p></div><button class="secondary" onclick="openMessageInbox()">Back</button></div><div class="dash-list">${contacts.length?contacts.map(c=>`<button class="dash-row chat-conversation" onclick="openChat(${Number(c.id)})"><span><b>${c.role==='seller'?'🏪':'🛒'} ${escapeHtml(c.name)}</b><small>${c.role==='seller'?`${c.product_count} active listing${Number(c.product_count)===1?'':'s'}`:'CampusCart buyer'}</small></span><span>Chat ›</span></button>`).join(''):`<div class="empty"><b>No contacts available yet.</b><p>${currentUser.role==='seller'?'Customers will appear here after they place an order.':'Ask a seller to register and add a product, then they will appear here.'}</p><button class="secondary" onclick="document.getElementById('products').scrollIntoView({behavior:'smooth'});closeDashboard()">Browse products</button></div>`}</div>`;
    dashboardOverlay.classList.add('open');
  }catch(e){showToast(e.message)}
}

async function openChat(otherId,productId=null){
 if(!currentUser)return openAuth('login');
 if(Number(otherId)===Number(currentUser.id)){showToast('This is your own listing. Log in with a different buyer account to test messaging.');return}
 try{
  const d=await api('/api/messages/'+Number(otherId));
  const title=d.user?.name||chatContactName(otherId,'Conversation');chatContacts[otherId]=title;
  const messages=(d.messages||[]).map(m=>`<div class="chat-bubble ${Number(m.sender_id)===Number(currentUser.id)?'mine':'theirs'}"><b>${Number(m.sender_id)===Number(currentUser.id)?'You':escapeHtml(title)}</b><div>${escapeHtml(m.body)}</div><small>${chatTime(m.created_at)}</small></div>`).join('')||'<div class="empty">No messages yet. Say hello to start the conversation.</div>';
  dashboardContent.innerHTML=`<div class="dashboard-header"><div><h2>💬 ${escapeHtml(title)}</h2><p class="auth-sub">Buyer–seller conversation</p></div><button class="secondary" onclick="openMessageInbox()">All messages</button></div><div id="chatBox" class="chat-box">${messages}</div><form class="chat-form" onsubmit="sendChat(event,${Number(otherId)},${productId===null?'null':Number(productId)})"><textarea id="chatText" required maxlength="1000" placeholder="Write a message..."></textarea><button class="primary" type="submit">Send</button></form>`;
  dashboardOverlay.classList.add('open');setTimeout(()=>{const b=document.getElementById('chatBox');if(b)b.scrollTop=b.scrollHeight},30)
 }catch(e){showToast('Chat error: '+e.message)}
}
async function sendChat(e,to,pid){
 e.preventDefault();const input=document.getElementById('chatText');const body=input?.value.trim();if(!body)return;
 if(Number(to)===Number(currentUser?.id)){showToast('You cannot message yourself.');return}
 const button=e.target.querySelector('button[type="submit"]');if(button){button.disabled=true;button.textContent='Sending...'}
 try{await api('/api/messages',{method:'POST',body:JSON.stringify({receiver_id:Number(to),product_id:pid||null,body})});if(input)input.value='';showToast('Message saved successfully 💬');await openChat(to,pid)}
 catch(err){showToast('Message was not sent: '+err.message);if(button){button.disabled=false;button.textContent='Send'}}
}
// Dashboard overrides with message shortcuts
openSellerDashboard=async function(){try{const [p,o,a]=await Promise.all([api('/api/seller/products'),api('/api/orders'),api('/api/seller/analytics')]);const orders=o.orders||[];dashboardContent.innerHTML=`<div class="dashboard-header"><div><h2>Seller Dashboard 🏪</h2><p class="auth-sub">See who ordered your products and manage customer messages.</p></div><div><button class="secondary" onclick="openMessageInbox()">💬 Messages</button> <button class="primary" onclick="showAddProduct()">+ Add product</button></div></div><div class="stats-grid"><div><b>${p.products.length}</b><small>Listings</small></div><div><b>${orders.length}</b><small>Customer orders</small></div><div><b>${money(a.revenue)}</b><small>Revenue</small></div><div><b>${a.units}</b><small>Units sold</small></div></div><h3 class="dash-title">Customer orders</h3><div class="dash-list">${orders.length?orders.map(x=>`<div class="order-card seller-order"><div><b>Order #${x.id} · ${escapeHtml(x.buyer_name)}</b><span class="status">${escapeHtml(x.status)}</span></div><small>👤 Buyer: ${escapeHtml(x.buyer_name)} · ✉ ${escapeHtml(x.buyer_email||'')}</small><small>💰 Your value: ${money(x.seller_total||x.total)} · ${escapeHtml(x.payment_method)} · ${escapeHtml(x.payment_status)}</small><div class="order-actions"><button class="secondary" onclick="openChat(${x.buyer_id})">💬 Chat buyer</button></div></div>`).join(''):'<div class="empty">No customer orders yet.</div>'}</div><h3 class="dash-title">My products</h3><div class="dash-list">${p.products.map(x=>`<div class="dash-row"><span><b>${escapeHtml(x.name)}</b><small>${money(x.price)} · Stock ${x.stock}</small></span><button class="danger" onclick="deleteProduct(${x.id})">Delete</button></div>`).join('')||'<div class="empty">No products yet.</div>'}</div>`;dashboardOverlay.classList.add('open')}catch(e){showToast(e.message)}};
openBuyerDashboard=async function(){if(!currentUser)return openAuth('login');try{const d=await api('/api/orders');dashboardContent.innerHTML=`<div class="dashboard-header"><div><h2>Buyer Dashboard 🛍️</h2><p class="auth-sub">Track orders and message sellers.</p></div><button class="secondary" onclick="openMessageInbox()">💬 Messages</button></div><h3 class="dash-title">My orders</h3><div class="dash-list">${d.orders.length?d.orders.map(o=>`<div class="order-card"><div><b>Order #${o.id}</b><span class="status">${escapeHtml(o.status)}</span></div><small>${chatTime(o.created_at)} · ${escapeHtml(o.payment_method)} · ${money(o.total)}</small><div class="order-items">${(o.items||[]).map(i=>`${i.icon||'📦'} ${escapeHtml(i.name)} × ${i.quantity} · Seller: ${escapeHtml(i.seller_name||'CampusCart')} ${i.seller_id?`<button class="link-btn" onclick="openChat(${i.seller_id},${i.product_id})">💬 Chat seller</button>`:''}`).join('<br>')}</div></div>`).join(''):'<div class="empty">You have no orders yet.</div>'}</div>`;dashboardOverlay.classList.add('open')}catch(e){showToast(e.message)}};


/* ═══════════════════════════════════════════════════════════════
   Homepage Upgrade: hero mini-cards + fresh listings
   Appended after all existing code. Overrides loadProducts safely.
   ═══════════════════════════════════════════════════════════════ */
(function () {
  const originalLoad = loadProducts;
  loadProducts = async function () {
    try { await originalLoad(); } catch (e) {}
    try {
      renderHeroProducts();
      renderFreshListings();
    } catch (e) { console.warn('Homepage upgrade failed:', e); }
  };
  // Run once on load
  setTimeout(function () { loadProducts(); }, 100);
})();

function renderHeroProducts() {
  const target = document.getElementById('heroProducts');
  if (!target) return;
  const top = products.slice(0, 4);
  if (!top.length) {
    target.innerHTML = '<div class="cc-mini-empty">No listings yet</div>';
    return;
  }
  target.innerHTML = top.map(function (p) {
    const thumb = p.image_url
      ? '<img src="' + p.image_url + '" alt="">'
      : (p.icon || '📦');
    return (
      '<div class="cc-mini-card" onclick="scrollToProduct(' + p.id + ')">' +
        '<div class="cc-mini-thumb">' + thumb + '</div>' +
        '<div class="cc-mini-title">' + escapeHtml(p.name) + '</div>' +
        '<div class="cc-mini-price">' + money(p.price) + '</div>' +
      '</div>'
    );
  }).join('');
}

function renderFreshListings() {
  const target = document.getElementById('freshGrid');
  if (!target) return;
  const fresh = products.slice().sort(function (a, b) {
    return (b.id || 0) - (a.id || 0);
  }).slice(0, 8);

  if (!fresh.length) {
    target.innerHTML = '<div class="empty" style="grid-column:1/-1">No listings yet.</div>';
    return;
  }
  target.innerHTML = fresh.map(productCardHome).join('');
}

function productCardHome(p) {
  const img = p.image_url
    ? '<img class="product-img" src="' + p.image_url + '" alt="' + escapeHtml(p.name) + '">'
    : '<div class="product-img emoji-img">' + (p.icon || '📦') + '</div>';

  const badge = Number(p.stock) > 0
    ? '<span class="cc-badge cc-badge-new">Available</span>'
    : '<span class="cc-badge cc-badge-used">Sold out</span>';

  return (
    '<article class="product" data-product-id="' + p.id + '">' +
      '<div class="product-img-wrap">' + img + badge + '</div>' +
      '<div class="product-body">' +
        '<span class="tag">' + escapeHtml(p.category) + '</span>' +
        '<h3>' + escapeHtml(p.name) + '</h3>' +
        '<small class="seller-line">' + escapeHtml(p.seller_name || 'CampusCart') + ' · Stock ' + p.stock + '</small>' +
        '<div class="price-row">' +
          '<span class="price">' + money(p.price) + '</span>' +
          '<button class="add" onclick="addToCart(' + p.id + ')">+ Add</button>' +
        '</div>' +
      '</div>' +
    '</article>'
  );
}

function scrollToProduct(id) {
  const grid = document.getElementById('products');
  if (grid) grid.scrollIntoView({ behavior: 'smooth' });
  setTimeout(function () {
    const card = document.querySelector('.product[data-product-id="' + id + '"]');
    if (card) {
      card.style.outline = '3px solid #6757e8';
      card.style.outlineOffset = '3px';
      setTimeout(function () { card.style.outline = ''; }, 1500);
    }
  }, 400);
}
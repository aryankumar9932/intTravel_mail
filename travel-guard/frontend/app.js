let currentPlan = null;
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
async function loadDataOverview() {
  try {
    const data = await request('/api/data-overview');
    const entries = Object.entries(data);
    const ready = entries.filter(([, info]) => info.loaded).length;
    $('data-status').textContent = `● ${ready}/${entries.length} loaded`;
    $('data-status').classList.toggle('data-ready', ready === entries.length);
    $('data-overview').innerHTML = entries.map(([name, info]) => `<div class="data-row ${info.loaded ? 'loaded' : 'missing'}"><strong>${escapeHtml(name)}</strong><span>${info.loaded ? '● Loaded' : '○ Missing'}</span><small>${info.rows} rows · ${escapeHtml(info.used_for)}</small></div>`).join('');
  } catch (error) {
    $('data-status').textContent = '● Data API unavailable';
    $('data-overview').innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`;
  }
}
function render(plan) {
  currentPlan = plan;
  $('results').classList.remove('hidden');
  $('plan-title').textContent = `${plan.days.length}-day ${plan.destination} escape`;
  $('source').textContent = `✦ ${plan.source}`;
  $('expected-route').innerHTML = plan.expected_route.map(route => `<div class="route-day"><strong>DAY ${route.day}</strong><span>${route.locations.map(escapeHtml).join(' → ')}</span></div>`).join('');
  $('recommendations').innerHTML = plan.ml_recommendations && plan.ml_recommendations.length ? plan.ml_recommendations.map(item => `<div class="ml-result highlighted"><span class="recommend-badge">★ HIGHLIGHTED</span><strong>${escapeHtml(item.place_name)}</strong><span>${escapeHtml(item.nearby_label || `Recommended near ${plan.destination}`)} · POI ID ${item.poi_id}</span><small>Category ${item.category_id} · Region ${item.geographic_id}</small><b>${(item.recommendation_score * 100).toFixed(1)}%</b></div>`).join('') : '<p class="muted">Run the data pipeline to train recommendations.</p>';
  $('itinerary').innerHTML = plan.days.map(day => `<article class="day card"><div class="day-num">DAY ${day.day.toString().padStart(2,'0')}</div><div><h3>${escapeHtml(day.title)}</h3><p>${escapeHtml(day.description)}</p><div>${day.stops.map(stop => `<span class="stop ${stop.flagged ? 'flagged' : 'safe'}">● ${escapeHtml(stop.name)} ${stop.rerouted ? '<span class="tag">Rerouted</span>' : ''}</span>`).join('')}</div></div></article>`).join('');
  const hotelSearch = new URL('https://www.google.com/maps/search/');
  hotelSearch.searchParams.set('api', '1');
  hotelSearch.searchParams.set('query', `hotels in ${plan.destination}`);
  $('hotels').innerHTML = `<a class="hotel-search" href="${escapeHtml(hotelSearch.href)}" target="_blank" rel="noopener noreferrer">Browse hotels in ${escapeHtml(plan.destination)} <span>↗</span></a>${plan.hotels.length ? plan.hotels.map(hotel => `<div class="item"><div><strong>${escapeHtml(hotel.name)}</strong><small>Near ${escapeHtml(hotel.place || plan.destination)} · ${escapeHtml(hotel.amenities)} · ${hotel.price}</small></div><span class="rating">★ ${hotel.trust_score}</span></div>`).join('') : '<p class="muted">No local hotel picks yet. Browse current options for this location.</p>'}`;
  $('guides').innerHTML = plan.guides.length ? plan.guides.map(guide => `<div class="item"><div><strong>${escapeHtml(guide.name)}</strong><small>${escapeHtml(guide.specialty)} · ${escapeHtml(guide.languages)}</small></div><div><select class="guide-day">${plan.days.map(day => `<option value="${day.day}">Day ${day.day}</option>`).join('')}</select><button class="book" data-guide="${escapeHtml(guide.id)}">Book</button></div></div>`).join('') : '<p class="muted">No verified guides for this destination yet.</p>';
  document.querySelectorAll('.book').forEach(button => button.addEventListener('click', () => bookGuide(button.dataset.guide, button.parentElement.querySelector('.guide-day').value)));
}
async function buildPlan(extra) {
  $('message').textContent = 'Building your safety-aware itinerary...';
  const payload = {destination: $('destination').value, days: Number($('days').value), travelerType: $('traveler').value, ...(extra || {})};
  try { const result = await request(extra ? '/api/disruptions' : '/api/plan', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}); render(result.plan || result); $('message').textContent = extra ? `Live alert added: ${result.alert.location} was rerouted safely.` : 'Your itinerary is ready.'; } catch (error) { $('message').textContent = error.message; }
}
async function bookGuide(id, day) { const result = await request('/api/book-guide', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({guide_id:id, day, destination:currentPlan.destination})}); $('message').textContent = `Guide booked for day ${day}: ${result.booking.booking_id}.`; }
$('plan-btn').addEventListener('click', () => buildPlan());
$('disrupt-btn').addEventListener('click', () => { const firstStop = currentPlan.days[0].stops[0].original_name; buildPlan({location:firstStop, score:20, message:'Emergency alert simulated for the demo.'}); });
loadDataOverview();

/* Real app.js with a small DOM/Leaflet seam: no browser, network, or map tiles. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = process.argv[2];
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.events = {}; this.attributes = {}; this.dataset = {}; this.hidden = false; this.disabled = false; this.currentTime = 0; this.duration = 30; this.textContent = ''; this.value = ''; this.style = { setProperty() {} }; const classes = new Set(); this.classList = { add: x => classes.add(x), remove: x => classes.delete(x), toggle: (x, yes) => { if (yes === undefined) yes = !classes.has(x); yes ? classes.add(x) : classes.delete(x); }, contains: x => classes.has(x) }; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(type, callback) { (this.events[type] ||= []).push(callback); }
  emit(type) { for (const cb of this.events[type] || []) cb({ currentTarget: this, target: this, preventDefault() {} }); }
  click() { if (!this.disabled) this.emit('click'); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return key === 'src' ? this.src : this.attributes[key]; }
  removeAttribute(key) { delete this.attributes[key]; if (key === 'src') this.src = ''; }
  querySelectorAll(tag) { return this.children.flatMap(child => child instanceof Element ? [...((tag.startsWith('.') ? (child.className || '').split(' ').includes(tag.slice(1)) : child.tagName === tag) ? [child] : []), ...child.querySelectorAll(tag)] : []); }
  querySelector(tag) { return this.querySelectorAll(tag)[0]; }
  focus() {}
  scrollIntoView() {}
  pause() {}
  load() {}
  play() { played.push(this.src); return Promise.resolve(); }
}
const elements = new Map();
const template = fs.readFileSync(`${root}/vacation_story/templates/index.html`, 'utf8');
for (const match of template.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)) { const e = new Element(match[1]); e.id = match[2]; e.hidden = match[0].includes(' hidden'); elements.set(e.id, e); }
const document = { getElementById: id => { assert(elements.has(id), `Missing template element ${id}`); return elements.get(id); }, createElement: tag => new Element(tag), body: new Element('body'), title: '' };
const played = [], markers = [], lines = [], fits = [], tileLayers = [];
const point = (x,y) => ({ x,y,distanceTo: other => Math.hypot(x-other.x,y-other.y) });
const mapEvents = {};
let zoom = 12, stalledBounds = false;
const views = [];
const map = {
 remove() {}, invalidateSize() {}, getZoom:()=>zoom, getMaxZoom:()=>19,
 attributionControl:{setPosition(){}},
 getBoundsZoom(){return stalledBounds ? zoom : 19;},
 setView(position,value){views.push({position,zoom:value});zoom=value;this.emit('zoomend');},
 on(types,callback){types.split(' ').forEach(type=>(mapEvents[type] ||= []).push(callback));return this;},
 emit(type){for(const callback of mapEvents[type] || [])callback();},
 zoomTo(value){zoom=value;this.emit('zoomend');},
 fitBounds(bounds, options){fits.push({bounds,options}); if(fits.length>1){zoom=options.maxZoom;this.emit('zoomend');}},
 latLngToLayerPoint: ([lat,lon]) => point((lon+71.07)*1000*2**(zoom-12)+350,(42.35-lat)*1000*2**(zoom-12)+300),
 layerPointToLatLng: p => [(300-p.y)/(1000*2**(zoom-12))+42.35,(p.x-350)/(1000*2**(zoom-12))-71.07],
 latLngToContainerPoint(value){return this.latLngToLayerPoint(value);},
 containerPointToLatLng(value){return this.layerPointToLatLng(value);},
};
const L = {
 map: () => map, point, latLngBounds: points => points,
 tileLayer: (url, options) => { tileLayers.push({url,options}); return {on(){return this;},addTo(){return this;}}; },
 divIcon: options => options,
 marker: (position, options) => {
   const item={position,options,events:{},element:new Element(),active:false,
     addTo(target){this.active=true;if(target.layers)target.layers.push(this);return this;},
     bindTooltip(value){this.tooltip=value;return this;},on(type,callback){this.events[type]=callback;return this;},
     getElement(){return this.element;},setZIndexOffset(value){this.zIndex=value;}};
   if(options.icon?.html)item.element.append(options.icon.html);
   markers.push(item);return item;
 },
 polyline: (positions, options) => { const line={positions,options,addTo(){return this;},setStyle(style){this.style=style;}};lines.push(line);return line; },
 layerGroup: () => ({layers:[],addTo(){return this;},clearLayers(){this.layers.forEach(item=>item.active=false);this.layers=[];}}),
};
const visiblePhotos=()=>markers.filter(marker=>marker.active && marker.options.title?.startsWith('Moment'));
const visibleClusters=()=>markers.filter(marker=>marker.active && marker.options.title?.includes('photos in this area'));
const story = {title:'A family journey',story_style:'connected_journal',journey_version:2,edition_id:'edition-two',narration:'available',opening:{text:'Our journey.'},closing:{text:'Looking back.'},
 moments:[
  {photo_id:'one',title:'Park frame',narrative:'We posed with the frame.',time:'2018-08-24T11:00:00',location:'Park',latitude:42.35,longitude:-71.07,photo_url:'/one.jpg',audio_url:'/moment-one.wav'},
  {photo_id:'two',title:'An evening walk',narrative:'We wandered together.',time:'2018-08-24T19:00:00',location:'Harbor',latitude:42.36,longitude:-71.05,photo_url:'/two.jpg',audio_url:'/moment-two.wav'},
  {photo_id:'four',title:'At the same place',narrative:'We paused here.',time:'2018-08-24T19:01:00',location:'Harbor',latitude:42.36,longitude:-71.05,photo_url:'/four.jpg',audio_url:'/moment-four.wav'},
  {photo_id:'five',title:'A nearby view',narrative:'We looked around.',time:'2018-08-25T12:00:00',location:'Harbor',latitude:42.360001,longitude:-71.05,photo_url:'/five.jpg',audio_url:'/moment-five.wav'},
  {photo_id:'three',title:'Another memory',narrative:'We shared a meal.',time:null,location:null,latitude:null,longitude:null,photo_url:'/three.jpg',audio_url:'/moment-three.wav'}],
 days:[{id:'day-2018-08-24',date:'2018-08-24',title:'A day together',narrative:'The whole day, told as one story.',moment_ids:['one','two','four'],audio_url:'/day-one.wav'},{id:'day-2018-08-25',date:'2018-08-25',title:'The next day',narrative:'Another day in the journey.',moment_ids:['five'],audio_url:'/day-two.wav'},{id:'undated',date:null,title:'Undated memories',narrative:'A memory with no known date.',moment_ids:['three'],audio_url:'/day-undated.wav'}]};
const trip={id:'a'.repeat(32),title:story.title,status:{state:'ready'},photos:[],story_available:true};
const localData=new Map();
const window={ L,addEventListener(){},matchMedia:()=>({matches:false}) };
const context={window,document,L,console,URLSearchParams,location:{hash:`#trip=${trip.id}`},localStorage:{getItem:k=>localData.get(k)||null,setItem:(k,v)=>localData.set(k,v),removeItem:k=>localData.delete(k)},setTimeout,clearTimeout,fetch:async url=>({ok:true,status:200,json:async()=>url.endsWith('/story')?story:trip})};
vm.createContext(context);
vm.runInContext(fs.readFileSync(`${root}/vacation_story/static/journal.js`,'utf8'),context);
vm.runInContext(fs.readFileSync(`${root}/vacation_story/static/photo-clusters.js`,'utf8'),context);
vm.runInContext(fs.readFileSync(`${root}/vacation_story/static/app.js`,'utf8'),context);
(async()=>{
 await new Promise(resolve=>setTimeout(resolve,15));
 assert.equal(played.length,0,'Overview never autoplays');
 assert.equal(tileLayers[0].url,'https://tile.openstreetmap.org/{z}/{x}/{y}.png');
 assert(tileLayers[0].options.attribution.includes('OpenStreetMap'));
 assert.equal(fits.length,1,'Fit the whole journey once; no narration-driven auto-panning');
 assert.equal(fits[0].bounds.length,4);
 assert.equal(visiblePhotos().length,0,'Overlapping photos do not remain as separate pins at overview zoom');
 assert.equal(visibleClusters().length,1,'Close GPS points collapse into one thumbnail group');
 assert.equal(visibleClusters()[0].options.icon.html.querySelector('.cluster-count').textContent,'4 photos');
 assert(visibleClusters()[0].element.classList.contains('day-active'),'Mixed-day group highlights any active-day member, not only its final photo');
 assert.equal(lines.length,3,'Routes still join the true four photo coordinates without card leader lines');
 assert.equal(JSON.stringify(lines[0].positions),JSON.stringify([[42.35,-71.07],[42.36,-71.05]]));
 const noAudio=played.length;
 visibleClusters()[0].events.click();
 assert.equal(played.length,noAudio,'Cluster expansion never starts narration');
 assert.equal(fits.length,2,'Cluster click zooms to member bounds');
 assert.equal(fits[1].bounds.length,4);
 assert.equal(visiblePhotos().length,1,'Distant photo separates when zoom gives it enough room');
 assert.equal(visibleClusters().length,1,'Co-located/dense photos remain grouped even at max zoom');
 const dense=visibleClusters()[0];
 dense.events.click();
 assert.equal(elements.get('map-photo-group').hidden,false,'Max-zoom cluster opens an accessible photo chooser');
 assert.equal(elements.get('map-photo-group-items').querySelectorAll('button').length,3);
 assert.equal(played.length,noAudio,'Opening the chooser does not autoplay');
 map.zoomTo(12);
 assert.equal(visiblePhotos().length,0,'Zooming out collapses pins again');
 assert.equal(visibleClusters().length,1);
 stalledBounds=true;
 visibleClusters()[0].events.click();
 assert.equal(map.getZoom(),13,'A cluster whose fitted bounds do not zoom still advances at least one level');
 assert.equal(views.length,1);
 assert.equal(played.length,noAudio);
 stalledBounds=false;
 map.zoomTo(16);
 assert.equal(visiblePhotos().length,1,'Zooming back in reveals adequately separated points');
 assert.equal(visibleClusters().length,1);
 assert.equal(elements.get('day-list').querySelectorAll('button').length,3);
 assert.equal(elements.get('day-moments').querySelectorAll('button').length,3,'Clustered photos remain available in their day strip');
 assert(elements.get('day-moments').querySelectorAll('button').every(button=>!button.querySelector('small')),'Clustered GPS photos are not labeled as missing locations');
 assert(elements.get('unlocated-note').textContent.includes('1 moment'));
 elements.get('listen-journey').click();
 assert.equal(played.at(-1),'/day-one.wav','Overview plays the whole-day WAV, not a moment');
 elements.get('narration').emit('ended');
 assert.equal(played.at(-1),'/day-two.wav','Whole journey advances to the next day');
 elements.get('narration').emit('ended');
 assert.equal(played.at(-1),'/day-undated.wav','Undated memories remain accessible after known days');
 assert.equal(fits.length,2,'Listening does not fetch tiles through automatic viewport changes');
 assert.equal(views.length,1,'Playback does not trigger map zooming');
 map.zoomTo(19);
 visibleClusters()[0].events.click();
 elements.get('map-photo-group-items').querySelectorAll('button')[0].click();
 assert.equal(played.at(-1),'/moment-two.wav','Pin click synchronously starts the selected moment');
 assert.equal(elements.get('moment-panel').hidden,false);
 assert.equal(elements.get('moment-narrative').textContent,'We wandered together.');
 assert.equal(elements.get('day-narrative').textContent,'The whole day, told as one story.');
 assert(visibleClusters()[0].element.classList.contains('moment-active'),'Day-strip or chooser selection highlights its shared cluster');
 assert.equal(visibleClusters()[0].zIndex,2000);
 assert.equal(elements.get('map-photo-group').hidden,true);
 const beforeChooser=played.length;
 visibleClusters()[0].events.click();
 assert.equal(played.length,beforeChooser,'Cluster click does not replace a playing moment');
 elements.get('map-photo-group-items').querySelectorAll('button')[1].click();
 assert.equal(played.at(-1),'/moment-four.wav','A second photo at exactly the same GPS point remains independently playable');
 const count=played.length;
 elements.get('back-to-day').click();
 assert.equal(elements.get('moment-panel').hidden,true);
 assert.equal(played.length,count,'Returning to day requires deliberate resume');
 elements.get('listen-day').click();
 assert.equal(played.at(-1),'/day-one.wav');
 assert.equal(story.moments[1].narrative,'We wandered together.','Rendering does not mutate published prose');
 const beforeIndividual=played.length;
 visiblePhotos()[0].events.click();
 assert.equal(played.at(-1),'/moment-one.wav','Individual pin still synchronously plays its own moment');
 assert.equal(played.length,beforeIndividual+1);
 assert.equal(story.moments[1].latitude,42.36,'Clustering never changes stored GPS');
 console.log('Zoom-aware groups, split/collapse, cluster zoom/chooser, true routes, day and moment playback passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

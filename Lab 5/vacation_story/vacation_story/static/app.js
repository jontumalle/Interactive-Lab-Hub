/* Buildless client. All generated and user text is inserted as plain text. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const VIBES = ['Relaxed', 'Exciting', 'Adventurous', 'Meaningful', 'Funny', 'Awe-inspiring'];
  const STAGES = { observe: 'Looking closely at your photos', synthesize: 'Connecting the details you shared', chapter: 'Writing your moments', outline: 'Finding the thread through your trip', framing: 'Bringing the journey together', day: 'Telling each day as one story', narration: 'Recording your narration' };
  let trip = null;
  let editing = null;
  let uploading = false;
  let failedUploads = [];
  let nextReviewId = null;
  let pollTimer = null;
  let revision = 0;
  let playing = false;
  let currentEdition = null;
  let lastPositionSave = 0;
  let journey = null;
  let map = null;
  let mapMarkers = new Map();
  let mapGroups = [];
  let routeLayers = [];
  let activeDay = 0;
  let activeMoment = null;
  let playbackMode = 'day';
  let loadedAudioKey = null;
  let dayOffsets = {};
  const DAY_COLORS = ['#246f68', '#b15e36', '#61589e', '#8c6e19', '#ad4772', '#297aa3'];
  const audio = $('narration');

  function show(id, visible = true) { $(id).hidden = !visible; }
  function notify(message = '', isError = false) {
    $('feedback').textContent = message;
    $('feedback').classList.toggle('error', isError);
    show('feedback', Boolean(message));
  }
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  async function api(path, options = {}) {
    const response = await fetch(path, options);
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(data?.error?.message || `Request failed (${response.status}). Please try again.`);
      error.status = response.status;
      throw error;
    }
    if (data === null) throw new Error('The device returned an unreadable response. Please try again.');
    return data;
  }
  function json(method, body = {}) { return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }; }
  function path(suffix = '') { return `/api/trips/${encodeURIComponent(trip.id)}${suffix}`; }
  async function action(button, work) {
    if (button.disabled) return;
    button.disabled = true;
    notify();
    try { await work(); }
    catch (error) { notify(error.message, true); }
    finally { button.disabled = false; }
  }
  function stopPolling() { clearTimeout(pollTimer); pollTimer = null; }
  function stopAudio(reset = false) {
    playing = false;
    audio.pause();
    if (reset) {
      audio.removeAttribute('src');
      audio.load();
    }
    show('pause-trip', false);
    show('play-trip');
  }

  async function listTrips() {
    const { trips } = await api('/api/trips');
    $('trips').replaceChildren();
    if (!trips.length) $('trips').append(node('li', 'Your next trip starts here.', 'muted'));
    for (const record of trips) {
      const item = node('li');
      const link = node('a', undefined, 'trip-link');
      link.href = `#trip=${encodeURIComponent(record.id)}`;
      link.append(node('strong', record.title), node('span', `${record.photo_count} photo${record.photo_count === 1 ? '' : 's'} · ${record.status.state}`));
      const remove = node('button', 'Delete', 'quiet');
      remove.setAttribute('aria-label', `Delete ${record.title}`);
      remove.disabled = ['queued', 'processing'].includes(record.status.state);
      remove.addEventListener('click', () => {
        if (!window.confirm(`Delete “${record.title}” and its photos and narration?`)) return;
        action(remove, async () => {
          await api(`/api/trips/${encodeURIComponent(record.id)}`, { method: 'DELETE' });
          await listTrips();
          notify('Trip and its photos deleted.');
        });
      });
      item.append(link, remove);
      $('trips').append(item);
    }
  }

  async function route() {
    const currentRevision = ++revision;
    stopPolling();
    saveListeningPosition();
    stopAudio(true);
    document.body.classList.remove('has-journal');
    notify();
    if (map) { map.remove(); map = null; }
    journey = null;
    mapMarkers = new Map();
    mapGroups = [];
    show('map-photo-group', false);
    routeLayers = [];
    loadedAudioKey = null;
    $('trip-title').hidden = false;
    editing = null;
    uploading = false;
    failedUploads = [];
    nextReviewId = null;
    $('upload-controls').disabled = false;
    show('upload-results', false);
    show('retry-uploads', false);
    const query = new URLSearchParams(location.hash.slice(1));
    const id = query.get('trip');
    show('home-view', !id);
    show('trip-view', Boolean(id));
    if (!id) {
      trip = null;
      document.title = 'Local Vacation Story';
      try { await listTrips(); } catch (error) { notify(error.message, true); }
      return;
    }
    $('trip-title').textContent = 'Opening your trip…';
    for (const view of ['collection', 'progress-view', 'story-view']) show(view, false);
    try {
      const record = await api(`/api/trips/${encodeURIComponent(id)}`);
      if (currentRevision !== revision) return;
      trip = record;
      $('trip-title').textContent = trip.title;
      document.title = `${trip.title} · Local Vacation Story`;
      $('trip-title').focus();
      if (trip.status.state === 'collecting') renderCollection();
      else if (trip.status.state === 'ready' && trip.requires_processing) {
        let status;
        try { status = await api(path('/process'), json('POST')); }
        catch (error) {
          if (error.status !== 409) throw error;
          status = await api(path('/status')); // Another tab may already be preparing this trip.
        }
        if (currentRevision !== revision) return;
        await renderStatus(status, currentRevision);
      } else await renderStatus(trip.status, currentRevision);
    } catch (error) { if (currentRevision === revision) notify(error.message, true); }
  }

  function renderCollection() {
    show('collection'); show('progress-view', false); show('story-view', false);
    show('saved-confirmation', false); show('photo-editor', false); show('upload-form');
    $('trip-subtitle').textContent = 'Gather your moments';
    $('photo-file').value = '';
    $('upload-status').textContent = '';
    editing = null;
    renderCollected();
  }
  function renderCollected() {
    const photos = trip.photos || [];
    show('collected-section', photos.length > 0);
    $('photo-count').textContent = `(${photos.length})`;
    show('finish-collection', !editing && !uploading && photos.length > 0);
    $('collected-photos').replaceChildren();
    photos.forEach((photo, index) => {
      const item = node('li');
      const image = node('img');
      image.src = photo.photo_url;
      image.alt = `Trip photo ${index + 1}`;
      image.loading = 'lazy';
      const label = photo.metadata.place_name || photo.metadata.captured_at || `Moment ${index + 1}`;
      const edit = node('button', 'Edit details', 'quiet');
      edit.disabled = uploading;
      edit.addEventListener('click', () => openEditor(photo));
      item.append(image, node('p', label), edit);
      $('collected-photos').append(item);
    });
  }

  function metadataField(key, label, value, type = 'text') {
    const wrapper = node('div');
    const inputId = `metadata-${key}`;
    const labelNode = node('label', label);
    labelNode.htmlFor = inputId;
    const input = node('input');
    input.id = inputId;
    input.name = key;
    input.type = type;
    input.value = value ?? '';
    if (type === 'number') { input.step = 'any'; input.min = key === 'latitude' ? '-90' : '-180'; input.max = key === 'latitude' ? '90' : '180'; }
    if (key === 'captured_at') {
      input.placeholder = '2026-10-30T14:30 (or leave unknown)';
      input.setAttribute('aria-describedby', 'capture-time-help');
      wrapper.append(labelNode, input, node('p', 'Use date and time as YYYY-MM-DDTHH:MM. Keep a timezone offset if known; leave blank if unknown.', 'muted'));
      wrapper.lastChild.id = 'capture-time-help';
    } else wrapper.append(labelNode, input);
    return wrapper;
  }
  function openEditor(photo) {
    if (uploading) return;
    editing = photo;
    show('saved-confirmation', false); show('upload-form', false); show('photo-editor');
    $('editor-image').src = photo.photo_url;
    $('missing-fields').replaceChildren();
    $('correction-fields').replaceChildren();
    $('metadata-summary').replaceChildren();
    const metadata = photo.metadata;
    const hasCoordinates = metadata.latitude != null && metadata.longitude != null;
    if (metadata.captured_at) $('metadata-summary').append(node('p', `Captured: ${metadata.captured_at}`));
    if (metadata.place_name) $('metadata-summary').append(node('p', `Place: ${metadata.place_name}`));
    if (hasCoordinates) $('metadata-summary').append(node('p', `Coordinates: ${metadata.latitude}, ${metadata.longitude}`));
    if (!metadata.captured_at && !metadata.place_name && !hasCoordinates) $('metadata-summary').append(node('p', 'No capture time or location was found in this photo.'));
    const fields = [
      ['captured_at', 'When was this taken? (if known)', metadata.captured_at, 'text'],
      ['place_name', hasCoordinates ? 'Place name (optional)' : 'Where was this? (if known)', metadata.place_name, 'text'],
      ['latitude', 'Latitude', metadata.latitude, 'number'],
      ['longitude', 'Longitude', metadata.longitude, 'number'],
    ];
    for (const [key, label, value, type] of fields) {
      const missingQuestion = (key === 'captured_at' || key === 'place_name') && !value;
      $(missingQuestion ? 'missing-fields' : 'correction-fields').append(metadataField(key, label, value, type));
    }
    $('metadata-corrections').open = false;
    const description = photo.user_description ?? metadata.embedded_description ?? '';
    $('description').value = description;
    $('description-label').textContent = metadata.embedded_description ? 'Photo context — edit anything you’d like' : 'What was happening here?';
    $('vibe-options').replaceChildren();
    VIBES.forEach(vibe => {
      const label = node('label', undefined, 'vibe-choice');
      const input = node('input');
      input.type = 'checkbox'; input.name = 'vibes'; input.value = vibe;
      input.checked = (photo.vibes || []).includes(vibe);
      label.append(input, node('span', vibe));
      $('vibe-options').append(label);
    });
    renderCollected();
    $('editor-title').focus();
  }

  async function finish(button) {
    if (uploading) return;
    await action(button, async () => {
      await api(path('/process'), json('POST'));
      editing = null;
      await route();
    });
  }
  async function pollStatus(currentRevision = revision) {
    stopPolling();
    const id = trip?.id;
    if (!id) return;
    try {
      const status = await api(`/api/trips/${encodeURIComponent(id)}/status`);
      if (currentRevision !== revision || trip?.id !== id) return;
      trip.status = status;
      await renderStatus(status, currentRevision);
    } catch (error) {
      if (currentRevision !== revision) return;
      notify(`${error.message} Progress will reconnect automatically.`, true);
      pollTimer = setTimeout(() => pollStatus(currentRevision), 5000);
    }
  }
  async function renderStatus(status, currentRevision) {
    if (status.state === 'ready') {
      stopPolling();
      const story = await api(path('/story'));
      if (currentRevision !== revision) return;
      renderStory(story);
      return;
    }
    show('collection', false); show('story-view', false); show('progress-view');
    $('trip-subtitle').textContent = status.state === 'failed' ? 'Your progress is saved' : 'Your story is taking shape';
    const failed = status.state === 'failed';
    $('progress-title').textContent = failed ? 'Your story needs a moment' : 'Creating your story';
    $('stage-label').textContent = STAGES[status.current_stage] || (status.state === 'queued' ? 'Waiting for the local story maker' : 'Getting started');
    $('progress-bar').max = status.total || 1;
    $('progress-bar').value = status.completed || 0;
    $('progress-count').textContent = status.total ? `${status.completed} of ${status.total} steps complete` : 'Preparing the next steps';
    show('processing-error', failed);
    $('processing-error').textContent = status.error?.message || 'Processing stopped. Your saved progress is still here.';
    show('retry', failed && status.error?.retryable === true);
    show('progress-note', !failed);
    stopPolling();
    if (!failed) pollTimer = setTimeout(() => pollStatus(currentRevision), 2500);
  }

  function itineraryTime(raw) {
    if (!raw) return '';
    const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(raw);
    if (!match) return raw;
    const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    return new Intl.DateTimeFormat(undefined, { month: 'long', day: 'numeric', year: 'numeric' }).format(date) + (match[4] ? ` · ${match[4]}` : '');
  }
  function currentDay() { return journey?.days[activeDay]; }
  function currentRecord() { return activeMoment !== null ? journey.moments[activeMoment] : currentDay(); }
  function currentKey() { return activeMoment !== null ? `moment:${currentRecord().photo_id}` : `day:${currentDay()?.id}`; }
  function saveListeningPosition() {
    if (!trip || !journey) return;
    if (loadedAudioKey && Number.isFinite(audio.currentTime)) dayOffsets[loadedAudioKey] = audio.currentTime;
    try { localStorage.setItem(`vacation-story-day-listening-${trip.id}`, JSON.stringify({ edition: currentEdition, day: activeDay, offsets: dayOffsets })); } catch (_) {}
  }
  function stopJourneyAudio(reset = true) {
    saveListeningPosition();
    stopAudio(reset);
    if (reset) loadedAudioKey = null;
  }
  function renderStory(story) {
    stopJourneyAudio();
    journey = window.VacationJourney.model(story);
    currentEdition = story.edition_id || 'original';
    activeDay = 0; activeMoment = null; playbackMode = 'day'; dayOffsets = {};
    try {
      const saved = JSON.parse(localStorage.getItem(`vacation-story-day-listening-${trip.id}`));
      if (saved?.edition === currentEdition && Number.isInteger(saved.day) && saved.day >= 0 && saved.day < journey.days.length) {
        activeDay = saved.day; dayOffsets = saved.offsets || {};
      }
    } catch (_) {}
    show('collection', false); show('progress-view', false); show('story-view');
    document.body.classList.add('has-journal');
    $('trip-title').hidden = true;
    $('trip-subtitle').textContent = 'One journey. A story for every day.';
    $('journey-title').textContent = story.title;
    $('journey-summary').textContent = `${journey.days.length} day ${journey.days.length === 1 ? 'story' : 'stories'} · ${journey.moments.length} moments`;
    show('narration-warning', story.narration !== 'available');
    show('moment-panel', false);
    $('day-list').replaceChildren();
    journey.days.forEach((day, index) => {
      const item = node('li'); const button = node('button', undefined, 'day-choice');
      button.style.setProperty('--day-color', DAY_COLORS[index % DAY_COLORS.length]);
      button.append(node('strong', day.date ? itineraryTime(day.date) : 'Undated memories'), node('span', `${day.moments.length} moments · ${day.title}`));
      button.addEventListener('click', () => selectDay(index)); item.append(button); $('day-list').append(item);
    });
    renderMap(); renderDay();
  }
  function renderMap() {
    if (map) { map.remove(); map = null; }
    mapMarkers = new Map(); mapGroups = []; routeLayers = [];
    show('map-photo-group', false);
    $('journey-map').replaceChildren();
    show('journey-map');
    $('show-whole-route').disabled = !journey.located.length || !window.L;
    show('map-unavailable', false);
    $('unlocated-note').textContent = journey.unlocated.length ? `${journey.unlocated.length} moment${journey.unlocated.length === 1 ? '' : 's'} have no GPS location. They remain available in their day's photo list.` : '';
    show('unlocated-note', journey.unlocated.length > 0);
    if (!journey.located.length || !window.L) {
      show('journey-map', false);
      $('map-unavailable').textContent = !journey.located.length ? 'No photo locations were recorded. Explore every moment in the day stories below.' : 'The map viewer could not load. All day stories and photographs remain available below.';
      show('map-unavailable'); return;
    }
    map = L.map('journey-map', { scrollWheelZoom: false });
    map.attributionControl?.setPosition('topright');
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      referrerPolicy: 'strict-origin-when-cross-origin',
    }).on('tileerror', () => { $('map-unavailable').textContent = 'Street-map tiles are unavailable. Photo pins and their route still work; reconnect for street detail.'; show('map-unavailable'); }).addTo(map);
    journey.located.forEach(moment => {
      if (L.circleMarker) L.circleMarker([moment.latitude, moment.longitude], { radius: 3, color: '#294e43', fillColor: '#fffdf7', fillOpacity: 1, weight: 1 }).addTo(map);
    });
    journey.route.forEach(segment => {
      const dayIndex = journey.days.findIndex(day => day.id === segment.day_id);
      const color = DAY_COLORS[Math.max(0, dayIndex) % DAY_COLORS.length];
      const line = L.polyline([[segment.from.latitude, segment.from.longitude], [segment.to.latitude, segment.to.longitude]], { color, weight: 3, opacity: .65, dashArray: segment.gap ? '5 7' : undefined }).addTo(map);
      routeLayers.push({ line, day_id: segment.day_id, segment });
    });
    // Arrows are computed in the rendered map projection, without a routing service.
    const arrows = L.layerGroup().addTo(map);
    function drawArrows() {
      arrows.clearLayers();
      journey.route.forEach(segment => {
        const start = map.latLngToLayerPoint([segment.from.latitude, segment.from.longitude]);
        const end = map.latLngToLayerPoint([segment.to.latitude, segment.to.longitude]);
        if (start.distanceTo(end) < 16) return;
        const middle = map.layerPointToLatLng(L.point((start.x + end.x) / 2, (start.y + end.y) / 2));
        const element = node('span', '➤', 'route-arrow');
        element.style.transform = `rotate(${Math.atan2(end.y - start.y, end.x - start.x) * 180 / Math.PI}deg)`;
        L.marker(middle, { interactive: false, keyboard: false, zIndexOffset: -1000, icon: L.divIcon({ html: element, className: 'route-arrow-icon', iconSize: [18, 18], iconAnchor: [9, 9] }) }).addTo(arrows);
      });
    }
    const photos = L.layerGroup().addTo(map);
    function renderPhotoGroups() {
      photos.clearLayers(); mapMarkers = new Map(); mapGroups = [];
      show('map-photo-group', false);
      const project = value => map.latLngToContainerPoint(value);
      for (const group of window.VacationPhotoClusters.group(journey.located, project)) {
        const members = group.moments;
        const grouped = members.length > 1;
        const icon = node('div', undefined, grouped ? 'photo-cluster' : 'photo-pin');
        if (grouped) {
          const preview = node('div', undefined, 'cluster-preview');
          members.slice(0, 3).forEach(moment => {
            const image = node('img'); image.src = moment.photo_url; image.alt = '';
            preview.append(image);
          });
          icon.append(preview, node('span', `${members.length} photos`, 'cluster-count'));
        } else {
          const image = node('img'); image.src = members[0].photo_url; image.alt = '';
          icon.append(image, node('span', String(members[0].index + 1), 'pin-number'));
        }
        const position = grouped ? map.containerPointToLatLng(L.point(group.x, group.y)) : [members[0].latitude, members[0].longitude];
        const title = grouped ? `${members.length} photos in this area. Select to explore.` : `Moment ${members[0].index + 1}: ${members[0].title}`;
        const marker = L.marker(position, {
          icon: L.divIcon({ html: icon, className: grouped ? 'photo-marker photo-cluster-marker' : 'photo-marker', iconSize: grouped ? [68, 80] : [58, 76], iconAnchor: grouped ? [34, 80] : [29, 76] }),
          title, keyboard: true, riseOnHover: true,
        }).addTo(photos);
        marker.bindTooltip(node('span', title));
        marker.on('click', () => {
          if (!grouped) { openMoment(members[0].index, true); return; }
          const maxZoom = map.getMaxZoom();
          const sameLocation = members.every(moment => moment.latitude === members[0].latitude && moment.longitude === members[0].longitude);
          if (map.getZoom() >= maxZoom || sameLocation) {
            showPhotoGroup(members);
          } else {
            // A cluster click only explores the map. It never starts narration.
            const bounds = L.latLngBounds(members.map(moment => [moment.latitude, moment.longitude]));
            const zoom = map.getZoom();
            const fittedZoom = Math.min(maxZoom, map.getBoundsZoom(bounds, false, L.point(160, 200)));
            if (fittedZoom <= zoom) {
              // A long chain can already fill the viewport. Still make progress
              // toward its center instead of fitting back out to the same view.
              map.setView(position, Math.min(maxZoom, zoom + 1));
            } else map.fitBounds(bounds, { padding: [80, 100], maxZoom });
          }
        });
        members.forEach(moment => mapMarkers.set(moment.photo_id, marker));
        mapGroups.push({ marker, moments: members });
      }
      highlightMap();
    }
    map.on('zoomend moveend resize', renderPhotoGroups);
    map.on('zoomend', drawArrows);
    fitRoute(); drawArrows(); renderPhotoGroups();
    setTimeout(() => { if (map) map.invalidateSize(); }, 0);
  }
  function fitRoute(dayOnly = false) {
    if (!map || !journey.located.length) return;
    const selected = dayOnly ? journey.located.filter(moment => journey.dayByMoment.get(moment.photo_id) === currentDay()?.id) : journey.located;
    if (!selected.length) return;
    map.fitBounds(L.latLngBounds(selected.map(moment => [moment.latitude, moment.longitude])), { padding: [65, 90], maxZoom: 16 });
  }
  function highlightMap() {
    routeLayers.forEach(({ line, day_id }) => line.setStyle({ weight: day_id === currentDay()?.id ? 5 : 2, opacity: day_id === currentDay()?.id ? .95 : .35 }));
    mapGroups.forEach(({ marker, moments }) => {
      const selected = activeMoment !== null && moments.some(moment => moment.index === activeMoment);
      marker.setZIndexOffset?.(selected ? 2000 : 0);
      const element = marker.getElement();
      element?.classList.toggle('day-active', moments.some(moment => journey.dayByMoment.get(moment.photo_id) === currentDay()?.id));
      element?.classList.toggle('moment-active', selected);
    });
  }
  function showPhotoGroup(moments) {
    $('map-photo-group-title').textContent = `${moments.length} photos in this area`;
    $('map-photo-group-items').replaceChildren();
    moments.forEach(moment => {
      const button = node('button', undefined, 'moment-thumb');
      const image = node('img'); image.src = moment.photo_url; image.alt = ''; image.loading = 'lazy';
      button.append(image, node('span', `Moment ${moment.index + 1}: ${moment.title}`));
      const day = journey.days.find(day => day.id === journey.dayByMoment.get(moment.photo_id));
      if (day) button.append(node('small', day.date ? itineraryTime(day.date) : 'Undated memories'));
      button.addEventListener('click', () => openMoment(moment.index, true));
      $('map-photo-group-items').append(button);
    });
    show('map-photo-group');
    $('map-photo-group-title').focus();
    $('map-photo-group').scrollIntoView({ behavior: 'auto', block: 'nearest' });
  }

  function renderDay() {
    const day = currentDay();
    if (!day) return;
    $('day-date').textContent = day.date ? itineraryTime(day.date) : 'Capture dates unknown';
    $('day-title').textContent = day.title;
    $('day-narrative').textContent = day.narrative;
    $('day-audio-error').textContent = day.audio_error || 'Day narration is unavailable; the story remains readable.';
    show('day-audio-error', !day.audio_url);
    $('listen-day').disabled = !day.audio_url;
    $('focus-day').disabled = !day.moments.some(moment => mapMarkers.has(moment.photo_id));
    $('day-moments').replaceChildren();
    day.moments.forEach(moment => {
      const button = node('button', undefined, 'moment-thumb');
      const image = node('img'); image.src = moment.photo_url; image.alt = ''; image.loading = 'lazy';
      button.append(image, node('span', `Moment ${moment.index + 1}: ${moment.title}`));
      if (!mapMarkers.has(moment.photo_id)) button.append(node('small', 'Location unavailable'));
      button.addEventListener('click', () => openMoment(moment.index, true));
      $('day-moments').append(button);
    });
    [...$('day-list').querySelectorAll('button')].forEach((button, index) => button.setAttribute('aria-current', index === activeDay ? 'step' : 'false'));
    highlightMap(); updatePlayer();
  }
  function selectDay(index) {
    if (!journey || index < 0 || index >= journey.days.length) return;
    show('map-photo-group', false);
    stopJourneyAudio(); activeDay = index; activeMoment = null; playbackMode = 'day';
    show('moment-panel', false); renderDay(); saveListeningPosition();
  }
  function openMoment(index, startAudio = false) {
    if (!journey?.moments[index]) return;
    show('map-photo-group', false);
    stopJourneyAudio(); activeMoment = index; playbackMode = 'moment';
    const moment = journey.moments[index];
    const dayIndex = journey.days.findIndex(day => day.moment_ids.includes(moment.photo_id));
    if (dayIndex >= 0) activeDay = dayIndex;
    renderDay();
    $('moment-label').textContent = `Moment ${index + 1} · ${currentDay()?.date ? itineraryTime(currentDay().date) : 'Undated'}`;
    $('moment-title').textContent = moment.title;
    $('moment-photo').src = moment.photo_url; $('moment-photo').alt = moment.title;
    $('moment-itinerary').textContent = [moment.location, itineraryTime(moment.time)].filter(Boolean).join(' · ');
    $('moment-narrative').textContent = moment.narrative;
    $('moment-audio-error').textContent = moment.audio_error || 'Moment narration is unavailable; read its story here.';
    show('moment-audio-error', !moment.audio_url); $('listen-moment').disabled = !moment.audio_url;
    show('moment-panel'); highlightMap(); updatePlayer();
    // This call stays synchronous with the thumbnail click for iPhone playback.
    if (startAudio) play();
    $('moment-panel').scrollIntoView({ behavior: 'auto', block: 'nearest' });
  }
  function updatePlayer() {
    const record = currentRecord(); if (!record) return;
    const momentMode = activeMoment !== null;
    $('reader-position').textContent = momentMode ? `Moment ${activeMoment + 1} / ${journey.moments.length} · ${record.title}` : `${currentDay().date ? itineraryTime(currentDay().date) : 'Undated memories'} · ${record.title}`;
    $('journey-progress').max = momentMode ? journey.moments.length : journey.days.length;
    $('journey-progress').value = momentMode ? activeMoment + 1 : activeDay + 1;
    $('previous').textContent = momentMode ? '← Previous moment' : '← Previous day';
    $('next').textContent = momentMode ? 'Next moment →' : 'Next day →';
    $('previous').disabled = momentMode ? activeMoment === 0 : activeDay === 0;
    $('next').disabled = momentMode ? activeMoment === journey.moments.length - 1 : activeDay === journey.days.length - 1;
    $('play-trip').disabled = !record.audio_url;
    $('play-trip').textContent = momentMode ? 'Listen to moment' : 'Listen to day';
    $('audio-note').textContent = record.audio_url ? 'Day stories follow the whole day. Choose a photograph to explore one moment.' : (record.audio_error || 'Narration is unavailable. Read the story and continue when ready.');
  }
  function play() {
    const record = currentRecord(); if (!record?.audio_url) return;
    const key = currentKey();
    if (loadedAudioKey !== key) {
      audio.src = record.audio_url; loadedAudioKey = key;
      const offset = Number(dayOffsets[key]) || 0;
      if (offset) audio.addEventListener('loadedmetadata', () => { if (loadedAudioKey === key && Number.isFinite(audio.duration)) audio.currentTime = Math.min(offset, Math.max(0, audio.duration - .1)); }, { once: true });
    }
    playing = true; show('play-trip', false); show('pause-trip');
    audio.play().then(() => { if (playing) $('audio-note').textContent = playbackMode === 'journey' ? 'Listening day by day across the whole journey.' : activeMoment !== null ? 'Listening to this moment. Return to the day overview whenever you like.' : 'Listening to this day as one story.'; }).catch(() => { stopAudio(); $('audio-note').textContent = 'Audio could not play. Read the story, or press Listen to try again.'; });
  }
  audio.addEventListener('timeupdate', () => { if (Date.now() - lastPositionSave > 2000) { lastPositionSave = Date.now(); saveListeningPosition(); } });
  audio.addEventListener('ended', () => {
    if (!playing) return;
    if (loadedAudioKey) dayOffsets[loadedAudioKey] = 0;
    loadedAudioKey = null;
    if (playbackMode === 'journey' && activeDay + 1 < journey.days.length) {
      activeDay++; activeMoment = null; stopAudio(); renderDay(); play();
    } else { stopAudio(); $('audio-note').textContent = 'This story is complete. Explore a photograph or choose another day.'; }
  });
  audio.addEventListener('error', () => { if (audio.getAttribute('src')) { stopAudio(); $('audio-note').textContent = 'Audio is unavailable right now. Your day and moment stories are still readable.'; } });
  $('listen-journey').addEventListener('click', () => { selectDay(0); playbackMode = 'journey'; play(); });
  $('listen-day').addEventListener('click', () => { stopJourneyAudio(); activeMoment = null; playbackMode = 'day'; show('moment-panel', false); updatePlayer(); play(); });
  $('listen-moment').addEventListener('click', play);
  $('play-trip').addEventListener('click', play);
  $('pause-trip').addEventListener('click', () => { saveListeningPosition(); stopAudio(); $('play-trip').textContent = 'Resume narration'; });
  $('previous').addEventListener('click', () => activeMoment !== null ? openMoment(activeMoment - 1) : selectDay(activeDay - 1));
  $('next').addEventListener('click', () => activeMoment !== null ? openMoment(activeMoment + 1) : selectDay(activeDay + 1));
  $('back-to-day').addEventListener('click', () => { selectDay(activeDay); $('day-title').focus(); });
  $('close-photo-group').addEventListener('click', () => show('map-photo-group', false));
  $('show-whole-route').addEventListener('click', () => fitRoute());
  $('focus-day').addEventListener('click', () => fitRoute(true));
  $('retry-narration').addEventListener('click', event => action(event.currentTarget, async () => { stopJourneyAudio(); await api(path('/narration/retry'), json('POST')); await route(); }));
  $('create-trip').addEventListener('submit', event => {
    event.preventDefault();
    action(event.target.querySelector('button'), async () => {
      const record = await api('/api/trips', json('POST', { title: $('title').value }));
      $('create-trip').reset();
      location.hash = `trip=${encodeURIComponent(record.id)}`;
    });
  });
  $('refresh-trips').addEventListener('click', event => action(event.currentTarget, listTrips));
  async function uploadFiles(files) {
    if (uploading || !files.length) return;
    const currentRevision = revision;
    const uploadPath = path('/photos');
    uploading = true;
    $('upload-controls').disabled = true;
    show('upload-results', false);
    notify();
    renderCollected();
    try {
      const result = await window.VacationUploads.uploadBatch(files, {
        isCurrent: () => currentRevision === revision,
        submit: async file => {
          const body = new FormData(); body.append('photo', file);
          return api(uploadPath, { method: 'POST', body });
        },
        onProgress: ({ index, total, file }) => {
          $('upload-status').textContent = `Uploading ${index} of ${total}: ${file.name}`;
        },
        onPhoto: photo => {
          trip.photos = [...(trip.photos || []), photo];
          renderCollected();
        },
      });
      if (result.cancelled || currentRevision !== revision) return;
      failedUploads = result.failures.map(failure => failure.file);
      $('photo-file').value = '';
      $('upload-summary').textContent = `${result.uploaded.length} of ${files.length} photos uploaded.`;
      $('upload-failures').replaceChildren();
      for (const failure of result.failures) {
        $('upload-failures').append(node('li', `${failure.file.name}: ${failure.message}`));
      }
      if (failedUploads.length) {
        $('upload-failures').append(node('li', 'Successful photos are saved. Retry failed photos from the upload form.'));
      }
      show('upload-results');
      show('retry-uploads', failedUploads.length > 0);
      uploading = false;
      if (result.uploaded.length) openEditor(result.uploaded[0]);
    } catch (error) {
      if (currentRevision === revision) notify(error.message, true);
    } finally {
      if (currentRevision === revision) {
        uploading = false;
        $('upload-controls').disabled = false;
        $('upload-status').textContent = '';
        renderCollected();
      }
    }
  }
  $('upload-form').addEventListener('submit', event => {
    event.preventDefault();
    uploadFiles([...$('photo-file').files]);
  });
  $('retry-uploads').addEventListener('click', () => uploadFiles([...failedUploads]));
  $('photo-answers').addEventListener('submit', event => {
    event.preventDefault();
    action(event.target.querySelector('button'), async () => {
      const currentRevision = revision;
      const metadata = {};
      for (const key of ['captured_at', 'place_name', 'latitude', 'longitude']) {
        const raw = $(`metadata-${key}`).value.trim();
        const value = raw === '' ? null : (key === 'latitude' || key === 'longitude') ? Number(raw) : raw;
        if (value !== editing.metadata[key]) metadata[key] = value;
      }
      const vibes = [...document.querySelectorAll('input[name="vibes"]:checked')].map(input => input.value);
      const photo = await api(path(`/photos/${encodeURIComponent(editing.id)}`), json('PATCH', {
        metadata, user_description: $('description').value.trim(), vibes,
      }));
      if (currentRevision !== revision) return;
      trip.photos = trip.photos.map(item => item.id === photo.id ? photo : item);
      const savedIndex = trip.photos.findIndex(item => item.id === photo.id);
      const remaining = trip.photos.length - savedIndex - 1;
      nextReviewId = trip.photos[savedIndex + 1]?.id || null;
      show('review-next', Boolean(nextReviewId));
      $('review-status').textContent = remaining
        ? `${remaining} more photo${remaining === 1 ? '' : 's'} to review. You can also finish with the available details.`
        : 'All photos are uploaded. Add more or create your story.';
      editing = null;
      show('photo-editor', false); show('upload-form', false); show('saved-confirmation');
      renderCollected();
      show('finish-collection', false);
      $('add-another').focus();
    });
  });
  $('review-next').addEventListener('click', () => {
    const photo = trip.photos.find(item => item.id === nextReviewId);
    if (photo) openEditor(photo);
  });
  $('add-another').addEventListener('click', () => { renderCollection(); $('photo-file').focus(); });
  $('finish-saved').addEventListener('click', event => finish(event.currentTarget));
  $('finish-collection').addEventListener('click', event => finish(event.currentTarget));
  $('retry').addEventListener('click', event => action(event.currentTarget, async () => {
    await api(path('/retry'), json('POST'));
    await pollStatus();
  }));
  $('check-progress').addEventListener('click', event => action(event.currentTarget, () => pollStatus()));
  window.addEventListener('hashchange', route);
  window.addEventListener('pagehide', () => { saveListeningPosition(); stopPolling(); stopAudio(); });
  route();
})();

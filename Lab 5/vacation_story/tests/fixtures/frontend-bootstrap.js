(() => {
  const pixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
  const metadata = { captured_at: null, latitude: null, longitude: null, place_name: 'Coast', embedded_description: null };
  const state = window.fixtureState = {
    trip: null, patch: null, ready: false, playCount: 0, uploads: 0, connected: true, preparations: 0,
    photo: { id: 'photo-001', submission_order: 0, metadata, extracted_metadata: { ...metadata }, user_description: '', vibes: [], photo_url: pixel },
  };
  HTMLMediaElement.prototype.play = function () { state.playCount++; return Promise.resolve(); };
  HTMLMediaElement.prototype.pause = function () {};
  HTMLMediaElement.prototype.load = function () {};
  window.confirm = () => true;
  window.IntersectionObserver = class { observe() {} disconnect() {} }; // Geometry is tested manually, not by these control checks.
  window.fetch = async (url, options = {}) => {
    const method = options.method || 'GET';
    const body = typeof options.body === 'string' ? JSON.parse(options.body) : null;
    let data;
    if (url === '/api/trips' && method === 'GET') data = { trips: state.trip ? [state.trip] : [] };
    else if (url === '/api/trips' && method === 'POST') {
      state.trip = { id: 'a'.repeat(32), title: body.title, photo_count: 0, photos: [], story_available: false,
        status: { state: 'collecting', current_stage: null, completed: 0, total: 0, error: null } };
      data = state.trip;
    } else if (url.endsWith('/photos') && method === 'POST') {
      state.uploads++;
      const photo = { ...state.photo, metadata: { ...metadata }, vibes: [], id: `photo-00${state.uploads}`, submission_order: state.uploads - 1 };
      state.trip.photos.push(photo); state.trip.photo_count = state.trip.photos.length; data = photo;
    } else if (/\/photos\/photo-00\d$/.test(url) && method === 'PATCH') {
      state.patch = body;
      const photo = state.trip.photos.find(photo => url.endsWith(photo.id));
      Object.assign(photo, { ...body, metadata: { ...photo.metadata, ...body.metadata } }); data = photo;
    } else if (url.endsWith('/process')) {
      const legacy = state.trip.requires_processing === true;
      if (legacy) { state.preparations++; state.trip.requires_processing = false; }
      state.connected = true; state.ready = false;
      state.trip.status = { state: 'processing', current_stage: legacy ? 'outline' : 'chapter', completed: legacy ? state.trip.photos.length * 2 : 1, total: 4 * state.trip.photos.length + 3 + Math.ceil(state.trip.photos.length / 12), error: null };
      data = state.trip.status;
    } else if (url.endsWith('/status')) {
      data = state.ready ? { state: 'ready', current_stage: null, completed: 4 * state.trip.photos.length + 3 + Math.ceil(state.trip.photos.length / 12), total: 4 * state.trip.photos.length + 3 + Math.ceil(state.trip.photos.length / 12), error: null } : state.trip.status;
    } else if (url.endsWith('/story')) {
      if (!state.connected) throw new Error('Intermediate captions must never reach the reader');
      data = { title: state.trip.title, story_style: state.connected ? 'connected_journal' : undefined, journey_version: 2, opening: { text: state.connected ? 'Our weekend unfolded along the coast.' : 'A weekend away.', audio_url: '/fixture-opening.wav' },
        chapters: state.trip.photos.map(photo => ({ photo_id: photo.id, title: 'By the coast', narrative: photo.user_description || 'Another moment.', location: 'Coast', time: null, photo_url: pixel, latitude: null, longitude: null, audio_url: '/fixture-chapter.wav' })),
        days: [{id:'undated', date:null, title:'Our memories together', narrative:'The day overview tells the memories together.', moment_ids:state.trip.photos.map(photo=>photo.id), audio_url:'/fixture-day.wav'}],
        closing: { text: 'A moment to revisit.', audio_url: null, audio_error: 'Narration is unavailable. Retry missing narration.' }, narration: 'partial' };
    } else if (url === `/api/trips/${state.trip?.id}`) data = state.trip;
    else throw new Error(`Unexpected fixture request: ${method} ${url}`);
    return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(data)) };
  };
})();

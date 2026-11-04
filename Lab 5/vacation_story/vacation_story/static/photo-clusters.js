/* Cluster overlapping thumbnail footprints in map pixels, never in GPS space. */
window.VacationPhotoClusters = {
  group(moments, project) {
    const points = moments.map(moment => ({ moment, point: project([moment.latitude, moment.longitude]) }));
    const parent = points.map((_, index) => index);
    function root(index) {
      while (parent[index] !== index) { parent[index] = parent[parent[index]]; index = parent[index]; }
      return index;
    }
    // Cards, pointer and stack shadows fit within 74 x 92 pixels. Keep a gap.
    const separated = (a, b) => Math.abs(a.x - b.x) >= 82 || Math.abs(a.y - b.y) >= 100;
    for (let a = 0; a < points.length; a++) {
      for (let b = a + 1; b < points.length; b++) {
        if (!separated(points[a].point, points[b].point)) parent[root(b)] = root(a);
      }
    }
    let groups = [];
    const byRoot = new Map();
    points.forEach((entry, index) => {
      const key = root(index);
      if (!byRoot.has(key)) byRoot.set(key, []);
      byRoot.get(key).push(entry);
    });
    function summarize(entries) {
      return { entries, moments: entries.map(entry => entry.moment),
        x: entries.reduce((sum, entry) => sum + entry.point.x, 0) / entries.length,
        y: entries.reduce((sum, entry) => sum + entry.point.y, 0) / entries.length };
    }
    groups = [...byRoot.values()].map(summarize);
    // Centroids of irregular groups can overlap even when their outer members do
    // not; merge those markers too so the displayed groups also have room.
    let merged = true;
    while (merged) {
      merged = false;
      outer: for (let a = 0; a < groups.length; a++) {
        for (let b = a + 1; b < groups.length; b++) {
          if (!separated(groups[a], groups[b])) {
            groups[a] = summarize([...groups[a].entries, ...groups[b].entries]);
            groups.splice(b, 1); merged = true; break outer;
          }
        }
      }
    }
    return groups.map(group => ({ moments: group.moments.sort((a, b) => a.index - b.index), x: group.x, y: group.y }));
  },
};

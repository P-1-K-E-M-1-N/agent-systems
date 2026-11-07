/* {{TITLE}}: starter script. Replace with the lane's app. Pattern:
   1. Factory.registerSW();
   2. const data = await Factory.loadJSON('data/latest.json');   (written by the lane's refresh.py)
   3. render the map from inlined GeoJSON (data/mi_counties.json via core.geo) with Leaflet from cdnjs;
   4. only after Factory.canLoadImage(tileUrl) resolves true, add raster layers (OSM, NOAA radar). */
(async function () {
  Factory.registerSW();
  const panel = Factory.qs('#panel');
  panel.textContent = 'Loading…';
  try {
    const data = await Factory.loadJSON('data/latest.json');
    panel.textContent = JSON.stringify(data).slice(0, 400);
  } catch (e) {
    panel.innerHTML = '<div class="empty">No data yet: run the lane\'s refresh.py so it writes app/data/latest.json.</div>';
  }
})();

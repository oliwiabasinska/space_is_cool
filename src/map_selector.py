"""The map scripts: the dark glowing basemap, and choosing a region with the mouse."""

from __future__ import annotations

from branca.element import MacroElement
from folium.template import Template


class RegionSelector(MacroElement):
    """Mouse selection on the map, with no toolbar.

    A double click starts a new rectangle, which is then drawn by dragging, so a
    plain drag still pans the map. The selected rectangle (corners, if there is
    one) can be resized by its corners and moved by its centre. A resized
    rectangle is reported like a newly drawn one, so Python sees both the same way.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            var style = {color: "#d62728", weight: 2, fillOpacity: 0.15};
            var drawer = new L.Draw.Rectangle(map, {shapeOptions: style});
            map.doubleClickZoom.disable();
            map.on("dblclick", function () { drawer.enable(); });
            {% if this.corners %}
            var selected = L.rectangle({{ this.corners|tojson }}, style).addTo(map);
            selected.editing.enable();
            selected.on("edit", function () {
                map.fire("draw:created", {layer: selected, layerType: "rectangle"});
            });
            map.on("draw:drawstart", function () { selected.editing.disable(); });
            map.on("draw:drawstop", function () { selected.editing.enable(); });
            {% endif %}
        })();
        {% endmacro %}
    """)

    def __init__(self, corners=None):
        super().__init__()
        self.corners = corners


# Natural Earth 1:50m data (public domain). The app serves its own slimmed copies
# from app/static; for the outlines the originals are the fallback if that is
# switched off. labels.json holds, for each country, its name, the point to centre
# the name on and the width and height of land available there (in degrees of
# longitude on the Web Mercator map), and for each city its name, position and the
# zoom level Natural Earth suggests showing it from.
NATURAL_EARTH = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
OUTLINES = {
    "land": ["/app/static/land.geojson", NATURAL_EARTH + "ne_50m_land.geojson"],
    "borders": ["/app/static/borders.geojson",
                NATURAL_EARTH + "ne_50m_admin_0_boundary_lines_land.geojson"],
    "labels": ["/app/static/labels.json"],
}


class DarkBasemap(MacroElement):
    """A dark map with glowing coastlines, country borders, and country and city names.

    Use it on a map made with tiles=None. The outlines are fetched by the browser,
    which caches them, so redrawing the map does not send them again. The glow is
    one filter on the whole land layer, which is much lighter than one per island.
    A country's name is centred on its largest piece of land and appears only
    once the map is zoomed in enough for the name to fit inside the country.
    City names follow from zoom 4, and one that would overlap a name already
    placed is left out.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            map.getContainer().style.background = "#080b10";

            function pane(name, zIndex) {
                var element = map.createPane(name);
                element.style.zIndex = zIndex;
                element.style.pointerEvents = "none";
                return element;
            }
            pane("land", 210).style.filter =
                "drop-shadow(0 0 2px #fff) drop-shadow(0 0 6px rgba(255, 255, 255, .9))";
            pane("borders", 220);
            pane("labels", 450);

            function load(urls) {
                return fetch(urls[0]).then(function (response) {
                    if (!response.ok) throw new Error(response.status);
                    return response.json();
                }).catch(function (error) {
                    if (urls.length > 1) return load(urls.slice(1));
                    throw error;
                });
            }
            var outlines = {{ this.outlines|tojson }};
            load(outlines.land).then(function (land) {
                L.geoJSON(land, {
                    pane: "land", interactive: false, attribution: "Natural Earth",
                    style: {color: "#fff", weight: 1.5, fillColor: "#11151b", fillOpacity: 1}
                }).addTo(map);
            }).catch(console.error);
            load(outlines.borders).then(function (borders) {
                L.geoJSON(borders, {
                    pane: "borders", interactive: false,
                    style: {color: "#fff", weight: 0.8, opacity: 0.45}
                }).addTo(map);
            }).catch(console.error);

            var css = document.createElement("style");
            css.textContent =
                ".map-label span { position: absolute; white-space: nowrap; color: #d5dbe3;" +
                "  font: 11px/16px sans-serif; text-shadow: 0 0 3px #000, 0 0 3px #000, 0 0 6px #000; }" +
                ".map-label.country span { transform: translate(-50%, -50%); font-weight: 600;" +
                "  letter-spacing: 1.5px; text-transform: uppercase; }" +
                ".map-label.city span { top: -8px; left: 7px; color: #aeb6c0; }" +
                ".map-label.city::before { content: ''; position: absolute; left: -2px; top: -2px;" +
                "  width: 4px; height: 4px; border-radius: 50%; background: #aeb6c0; }";
            document.head.appendChild(css);

            load(outlines.labels).then(function (names) {
                var layer = L.layerGroup().addTo(map);
                var ruler = document.createElement("canvas").getContext("2d");
                ruler.font = "600 11px sans-serif";
                function nameWidth(name) {  // as drawn: upper case, 1.5px between letters
                    return ruler.measureText(name.toUpperCase()).width + 1.5 * name.length;
                }
                function redraw() {
                    layer.clearLayers();
                    var zoom = map.getZoom(), view = map.getBounds().pad(0.1), taken = [];
                    var pixelsPerDegree = 256 * Math.pow(2, zoom) / 360;
                    function place(entry, kind) {
                        var where = [entry[1], entry[2]];
                        if (!view.contains(where)) return;
                        var point = map.latLngToContainerPoint(where);
                        var width = kind === "country" ? nameWidth(entry[0]) + 6 : entry[0].length * 6 + 12;
                        var left = kind === "country" ? point.x - width / 2 : point.x - 4;
                        var box = [left, point.y - 10, left + width, point.y + 10];
                        var overlaps = taken.some(function (other) {
                            return box[0] < other[2] && other[0] < box[2] && box[1] < other[3] && other[1] < box[3];
                        });
                        if (overlaps) return;
                        taken.push(box);
                        var text = document.createElement("span");
                        text.textContent = entry[0];
                        L.marker(where, {
                            pane: "labels", interactive: false, keyboard: false,
                            icon: L.divIcon({className: "map-label " + kind, html: text, iconSize: [0, 0]})
                        }).addTo(layer);
                    }
                    names.countries.forEach(function (country) {
                        var fits = nameWidth(country[0]) <= 0.9 * country[3] * pixelsPerDegree
                            && 14 <= country[4] * pixelsPerDegree;
                        if (fits) place(country, "country");
                    });
                    names.cities.forEach(function (city) {
                        if (zoom >= Math.max(city[3] + 1, 4)) place(city, "city");
                    });
                }
                map.on("moveend", redraw);
                redraw();
            }).catch(console.error);
        })();
        {% endmacro %}
    """)

    def __init__(self):
        super().__init__()
        self.outlines = OUTLINES

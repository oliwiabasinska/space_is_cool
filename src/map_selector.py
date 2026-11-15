"""The map script that lets a region be chosen and resized with the mouse."""

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

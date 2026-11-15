"""Landing page with the world-map slideshow and Explore navigation."""

import streamlit as st
import streamlit.components.v1 as components


def render_landing_page():
    """Render the full-screen map landing page and its Explore button."""
    st.markdown(
        """
        <style>
          html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            height: 100%;
            overflow: hidden;
            background: #080b10;
          }
          [data-testid="stHeader"], [data-testid="stToolbar"], footer {
            display: none;
          }
          [data-testid="stMainBlockContainer"] {
            max-width: none;
            padding: 0 !important;
          }
          [data-testid="stIFrame"] {
            position: fixed;
            inset: 0;
            z-index: 0;
            width: 100vw;
            height: 100vh !important;
          }
          [data-testid="stIFrame"] iframe {
            width: 100%;
            height: 100%;
            border: 0;
          }
          .st-key-explore_button {
            position: fixed;
            right: clamp(1rem, 3vw, 3rem);
            bottom: clamp(1rem, 3vh, 2rem);
            z-index: 10;
            width: auto;
          }
          .st-key-explore_button button {
            border: 0;
            background: transparent;
            box-shadow: none;
            color: transparent;
            -webkit-text-fill-color: transparent;
            -webkit-text-stroke: 1.2px #ff3030;
            text-shadow: 0 0 5px #ff2020, 0 0 12px #ff2020;
            font-size: 1.35rem;
            font-weight: 700;
            padding: 0.4rem 0.6rem;
          }
          .st-key-explore_button button:hover {
            border: 0;
            background: transparent;
            color: transparent;
            -webkit-text-fill-color: transparent;
            -webkit-text-stroke: 1.5px #ff5555;
            text-shadow: 0 0 7px #ff2020, 0 0 18px #ff2020;
          }
          .st-key-explore_button button:focus {
            box-shadow: none;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    components.html(
        """
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <style>
            html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; background: #080b10; }
            #world-map { width: 100%; height: 100%; background: #080b10; }
            .leaflet-container { background: #080b10; }
            .coastline-glow {
              filter: drop-shadow(0 0 2px #fff) drop-shadow(0 0 6px rgba(255, 255, 255, .9));
            }
            .laser-marker { background: transparent; border: 0; }
            .laser-marker span {
              display: block; width: 12px; height: 12px; margin: 3px;
              border-radius: 50%; background: #ff2020;
              box-shadow: 0 0 6px 3px rgba(255, 32, 32, .9), 0 0 18px 7px rgba(255, 32, 32, .55);
              animation: pulse 1.5s ease-in-out infinite;
            }
            @keyframes pulse {
              50% { box-shadow: 0 0 9px 5px rgba(255, 32, 32, 1), 0 0 24px 10px rgba(255, 32, 32, .65); }
            }
            .slide-indicators {
              position: absolute; z-index: 1000; bottom: 18px; left: 50%;
              display: flex; transform: translateX(-50%); align-items: center; gap: 12px;
            }
            .slide-dot {
              width: 10px; height: 10px; padding: 0; border: 0; border-radius: 50%;
              background: #59616b; cursor: default;
            }
            .slide-dot.active { background: #ff2020; box-shadow: 0 0 8px 3px rgba(255, 32, 32, .7); }
            #map-error {
              display: none; position: absolute; z-index: 1000; top: 10px; left: 50px;
              padding: 6px 10px; background: #241313; color: #fff; border-radius: 4px;
            }
          </style>
        </head>
        <body>
          <div id="world-map"></div>
          <div class="slide-indicators" role="status" aria-label="Slideshow position">
            <button class="slide-dot active" aria-label="Slide 1 of 3"></button>
            <button class="slide-dot" aria-label="Slide 2 of 3"></button>
            <button class="slide-dot" aria-label="Slide 3 of 3"></button>
          </div>
          <div id="map-error"></div>
          <script>
            const map = L.map("world-map", {
              center: [20, 0], zoom: 2, minZoom: 2, maxZoom: 6
            });
            const locations = [
              { name: "Amsterdam, Netherlands", coordinates: [52.3676, 4.9041] },
              { name: "Uluwatu, Bali, Indonesia", coordinates: [-8.8291, 115.0849] },
              { name: "San Francisco, United States", coordinates: [37.7749, -122.4194] }
            ];
            const laserIcon = L.divIcon({
              className: "laser-marker",
              html: "<span></span>",
              iconSize: [18, 18],
              iconAnchor: [9, 9]
            });
            locations.forEach(location => {
              L.marker(location.coordinates, { icon: laserIcon })
                .bindTooltip(location.name)
                .addTo(map);
            });

            fetch("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson")
              .then(response => {
                if (!response.ok) throw new Error(`Coastline data request failed (${response.status})`);
                return response.json();
              })
              .then(land => L.geoJSON(land, {
                style: {
                  color: "#fff",
                  weight: 1.5,
                  opacity: 1,
                  fillColor: "#11151b",
                  fillOpacity: 1,
                  className: "coastline-glow"
                }
              }).addTo(map))
              .catch(error => {
                const message = document.getElementById("map-error");
                message.textContent = `Unable to load glowing coastlines: ${error.message}`;
                message.style.display = "block";
                console.error(error);
              });

            const dots = Array.from(document.querySelectorAll(".slide-dot"));
            let currentSlide = 0;
            window.setInterval(() => {
              dots[currentSlide].classList.remove("active");
              currentSlide = (currentSlide + 1) % dots.length;
              dots[currentSlide].classList.add("active");
              dots.forEach((dot, index) => {
                dot.setAttribute(
                  "aria-label",
                  `Slide ${index + 1} of 3${index === currentSlide ? ", current" : ""}`
                );
              });
            }, 10000);
          </script>
        </body>
        </html>
        """,
        height=800,
        scrolling=False,
    )
    if st.button("Explore", key="explore_button"):
        st.session_state.page = "explore"
        st.rerun()

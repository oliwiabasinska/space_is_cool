"""Landing page with the Paris map and Explore navigation."""

import base64
import html
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


def _paris_popup_content():
    """Build popup content from the Paris text, photos, and chart."""
    paris_dir = Path(__file__).resolve().parent.parent / "Paris"
    info_path = paris_dir / "paris_info.txt"
    info_text = info_path.read_text(encoding="utf-8")
    paragraphs = [
        " ".join(line.strip() for line in block.splitlines()).strip()
        for block in info_text.split("\n\n")
    ]
    paris_paragraph = next(
        (paragraph for paragraph in paragraphs if paragraph.startswith("For decades,")),
        None,
    )
    however_paragraph = next(
        (paragraph for paragraph in paragraphs if paragraph.startswith("However,")),
        None,
    )
    remaining_paragraph = next(
        (paragraph for paragraph in paragraphs if paragraph.startswith("This change")),
        None,
    )
    if paris_paragraph is None or however_paragraph is None or remaining_paragraph is None:
        raise ValueError(f"Expected Paris paragraphs were not found in {info_path}.")

    however_sentence = re.match(r"However\b.*?[.!?](?=\s|$)", however_paragraph)
    if however_sentence is None:
        raise ValueError(f"Could not find the first sentence of the 'However' paragraph in {info_path}.")

    article_url = re.search(r"https?://\S+", info_text)
    if article_url is None:
        raise ValueError(f"Could not find the article URL in {info_path}.")

    def image_data_uri(filename):
        image_path = paris_dir / filename
        image_data = image_path.read_bytes()
        if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
            media_type = "image/png"
        elif image_data.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"
        else:
            raise ValueError(f"Unsupported image format: {image_path}")
        encoded_image = base64.b64encode(image_data).decode("ascii")
        return f"data:{media_type};base64,{encoded_image}"

    return (
        f"<div class='paris-popup-content'>"
        f"<h2>Paris, France</h2>"
        f"<p>{html.escape(paris_paragraph)}</p>"
        f"<p>{html.escape(however_sentence.group(0))}</p>"
        f"<div class='comparison-photos'>"
        f"<figure><img src='{image_data_uri('before.jpeg')}' alt='Paris in May 2017'>"
        f"<figcaption>May 2017</figcaption></figure>"
        f"<figure><img src='{image_data_uri('after.jpeg')}' alt='Paris in August 2022'>"
        f"<figcaption>August 2022</figcaption></figure>"
        f"</div>"
        f"<img class='paris-chart' src='{image_data_uri('paris_temp.jpeg')}' "
        f"alt='Monthly maximum temperature anomaly in Paris and trend line'>"
        f"<p>{html.escape(remaining_paragraph)}</p>"
        f"<p class='more-information'>More information: "
        f"<a href='{html.escape(article_url.group(0), quote=True)}' target='_blank' "
        f"rel='noopener noreferrer'>{html.escape(article_url.group(0))}</a></p>"
        f"</div>"
    )


def render_landing_page():
    """Render the full-screen map landing page and its Explore button.

    Explore is a real Streamlit button, because the map's frame is sandboxed and
    cannot navigate the page itself. The button stays hidden until the map's
    script marks the page as "paris-visited" (a class on <body>), which it does
    two seconds after the Paris marker is first clicked.
    """
    paris_popup_content = _paris_popup_content()

    st.markdown(
        """
        <style>
          html, body, #root, [data-testid="stApp"], [data-testid="stAppViewContainer"],
          [data-testid="stMain"], [data-testid="stMainBlockContainer"], [data-testid="stVerticalBlock"] {
            width: 100%;
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
          [data-testid="stAppViewContainer"], [data-testid="stMain"],
          [data-testid="stMainBlockContainer"], [data-testid="stVerticalBlock"] {
            max-width: none !important;
            margin: 0 !important;
            padding: 0 !important;
          }
          [data-testid="stMain"] > div,
          [data-testid="stMainBlockContainer"] > div,
          [data-testid="stVerticalBlock"] {
            width: 100%;
            max-width: none;
            padding: 0;
            margin: 0;
          }
          [data-testid="stIFrame"] {
            position: fixed;
            inset: 0;
            z-index: 0;
            width: 100vw;
            height: 100vh !important;
            height: 100dvh !important;
            margin: 0 !important;
            padding: 0 !important;
          }
          [data-testid="stIFrame"] iframe {
            width: 100%;
            height: 100%;
            border: 0;
          }
          .st-key-explore_button {
            display: none;
            position: fixed;
            left: clamp(18px, 3vw, 48px);
            bottom: clamp(18px, 3vh, 40px);
            z-index: 10;
            width: auto !important;
            height: auto !important;
            margin: 0;
          }
          body.paris-visited .st-key-explore_button {
            display: block;
          }
          .st-key-explore_button button,
          .st-key-explore_button button:hover,
          .st-key-explore_button button:active,
          .st-key-explore_button button:focus {
            border: 0;
            background: transparent;
            box-shadow: none;
            padding: 0;
            min-height: 0;
            cursor: pointer;
          }
          .st-key-explore_button button p {
            color: transparent;
            -webkit-text-fill-color: transparent;
            -webkit-text-stroke: 2px #ff3030;
            text-shadow: 0 0 8px #ff2020, 0 0 20px #ff2020;
            font-size: 40pt;
            font-weight: 700;
            line-height: 1.2;
            white-space: nowrap;
          }
          .st-key-explore_button button:hover p {
            -webkit-text-stroke-color: #ff6666;
            text-shadow: 0 0 10px #ff2020, 0 0 24px #ff2020;
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
          <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <style>
            html, body {
              position: fixed; inset: 0; width: 100%; height: 100%;
              margin: 0; padding: 0; overflow: hidden; background: #080b10;
            }
            #world-map { width: 100%; height: 100%; background: #080b10; }
            .leaflet-container { background: #080b10; }
            #welcome-message {
              position: fixed;
              z-index: 1100;
              top: 50%;
              left: 50%;
              transform: translate(-50%, -50%);
              box-sizing: border-box;
              width: min(760px, calc(100vw - 32px));
              padding: 22px 30px;
              color: #fff;
              background: rgba(0, 0, 0, .7);
              text-align: center;
              font-size: clamp(20px, 2.4vw, 32px);
              line-height: 1.35;
              pointer-events: none;
              transition: opacity .25s ease;
            }
            #welcome-message.hidden {
              opacity: 0;
              visibility: hidden;
            }
            #paris-panel {
              display: none;
              position: fixed;
              z-index: 1200;
              top: 50%;
              right: clamp(16px, 3vw, 48px);
              transform: translateY(-50%);
              box-sizing: border-box;
              width: min(900px, 62vw);
              max-height: 90vh;
              max-height: 90dvh;
              overflow-y: auto;
              padding: 30px;
              color: #fff;
              background: rgba(8, 11, 16, .97);
              border: 2px solid #fff;
              box-shadow: 0 0 4px #fff, 0 0 16px rgba(255, 255, 255, .95);
              font-size: 22pt;
              line-height: 1.4;
              scrollbar-color: #fff #11151b;
            }
            #paris-panel h2 {
              margin: 0 48px 20px 0;
              color: #fff;
              font-size: 32pt;
              line-height: 1.2;
            }
            #paris-panel p { margin: 16px 0 20px; }
            #paris-panel .panel-close {
              position: sticky;
              float: right;
              top: 0;
              z-index: 2;
              margin: -14px -14px 0 0;
              padding: 2px 12px;
              color: #fff;
              background: transparent;
              border: 0;
              font-size: 32pt;
              cursor: pointer;
            }
            .comparison-photos {
              display: flex;
              gap: 18px;
              margin: 22px 0;
            }
            .comparison-photos figure {
              flex: 1 1 0;
              min-width: 0;
              margin: 0;
              text-align: center;
            }
            .comparison-photos img {
              display: block;
              width: 100%;
              height: 22vh;
              object-fit: cover;
            }
            .comparison-photos figcaption {
              margin-top: 8px;
              font-size: 20pt;
            }
            #paris-panel img.paris-chart {
              float: left;
              width: 52%;
              height: auto;
              margin: 6px 20px 14px 0;
            }
            #paris-panel .more-information { clear: both; padding-top: 10px; }
            #paris-panel a { color: #b7d9ff; overflow-wrap: anywhere; }
            @media (max-width: 800px) {
              #paris-panel {
                right: 12px;
                width: min(900px, calc(100vw - 24px));
                max-height: 84vh;
                max-height: 84dvh;
                padding: 20px;
                font-size: 22pt;
              }
              #paris-panel h2 { font-size: 26pt; }
              .comparison-photos img { height: 17vh; }
              .comparison-photos figcaption { font-size: 16pt; }
              #paris-panel img.paris-chart {
                float: none;
                width: 100%;
                margin: 6px 0 14px;
              }
            }
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
            .paris-tooltip {
              font-size: 20pt;
              font-weight: 700;
            }
            @keyframes pulse {
              50% { box-shadow: 0 0 9px 5px rgba(255, 32, 32, 1), 0 0 24px 10px rgba(255, 32, 32, .65); }
            }
            #map-error {
              display: none; position: absolute; z-index: 1000; top: 10px; left: 50px;
              padding: 6px 10px; background: #241313; color: #fff; border-radius: 4px;
            }
          </style>
        </head>
        <body>
          <div id="world-map"></div>
          <div id="welcome-message">
            Become a Trend Detective. Click the red circle.
          </div>
          <div id="paris-panel">
            <button type="button" class="panel-close" aria-label="Close Paris information">&times;</button>
            __PARIS_POPUP_CONTENT__
          </div>
          <div id="map-error"></div>
          <script>
            const map = L.map("world-map", {
              center: [20, 0], zoom: 2, minZoom: 2, maxZoom: 6
            });
            window.addEventListener("resize", () => map.invalidateSize());
            window.setTimeout(() => map.invalidateSize(), 100);
            // The Explore button lives in the Streamlit page around this frame;
            // marking that page's <body> is what makes it appear.
            function showExplore() {
              try {
                window.parent.document.body.classList.add("paris-visited");
              } catch (error) {
                console.error("Could not reveal the Explore button:", error);
              }
            }
            if (sessionStorage.getItem("parisVisited") === "true") {
              showExplore();
            }
            const laserIcon = L.divIcon({
              className: "laser-marker",
              html: "<span></span>",
              iconSize: [18, 18],
              iconAnchor: [9, 9]
            });
            L.marker([48.8566, 2.3522], { icon: laserIcon })
              .bindTooltip("Paris, France", {
                className: "paris-tooltip",
                direction: "top",
                offset: [0, -8]
              })
              .on("click", () => {
                document.getElementById("welcome-message").classList.add("hidden");
                document.getElementById("paris-panel").style.display = "block";
                if (sessionStorage.getItem("parisVisited") !== "true") {
                  sessionStorage.setItem("parisVisited", "true");
                  window.setTimeout(showExplore, 2000);
                } else {
                  showExplore();
                }
              })
              .addTo(map);

            document.querySelector(".panel-close").addEventListener("click", () => {
              document.getElementById("paris-panel").style.display = "none";
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

          </script>
        </body>
        </html>
        """.replace("__PARIS_POPUP_CONTENT__", paris_popup_content),
        height=800,
        scrolling=False,
    )
    if st.button("Explore →", key="explore_button"):
        st.session_state.page = "explore"
        st.rerun()

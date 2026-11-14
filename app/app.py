
import streamlit as st
import folium
from streamlit_folium import st_folium

st.title("My interactive world map")
st.write("Testing the map display...")

# Create a map
m = folium.Map(location=[20, 0], zoom_start=2)

# Display the map and capture clicks
data = st_folium(m, width=700, height=450)

# Display selected coordinates
if data and data.get("last_clicked"):
    st.write("Selected coordinates:", data["last_clicked"])

# run streamlit run app.py in the terminal to launch the app

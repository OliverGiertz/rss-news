# log_viewer.py

import streamlit as st
import os

st.set_page_config(page_title="🧾 Log Viewer", layout="wide")
st.title("🧾 Letzte Logeinträge anzeigen")

LOG_FILE = "logs/rss_tool.log"
MAX_LINES = 500

if not os.path.exists(LOG_FILE):
    st.warning("Keine Logdatei gefunden.")
else:
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()

    st.write(f"Letzte {min(len(lines), MAX_LINES)} Zeilen aus `{LOG_FILE}`:")

    st.code("".join(lines[-MAX_LINES:]), language="text")

    if st.button("🔄 Neu laden"):
        st.rerun()

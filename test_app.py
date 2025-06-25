import streamlit as st, os
st.write("Listing root:", os.listdir("."))
if os.path.exists(".streamlit"):
    st.write(".streamlit listing:", os.listdir(".streamlit"))
st.write("Chromium:", os.path.exists("/usr/bin/chromium"))
st.write("Chromedriver:", os.path.exists("/usr/lib/chromium/chromedriver"))

import os
import streamlit as st
from policybuddy_cli import main

def main():
    st.title("Research Assistant")

    openai_api_key = st.text_input("OpenAI API Key", type="password")
    perplexity_api_key = st.text_input("Perplexity API Key", type="password")
    serper_api_key = st.text_input("Serper API Key", type="password")

    research_prompt = st.text_area("Enter your research prompt")

    if st.button("Generate Research Plan"):
        os.environ["OPENAI_API_KEY"] = openai_api_key
        os.environ["PERPLEXITY_API_KEY"] = perplexity_api_key
        os.environ["SERPER_API_KEY"] = serper_api_key

        main(research_prompt)

if __name__ == "__main__":
    main()

import os
import streamlit as st
from policybuddy_cli 
from supabase import create_client, Client
import requests
import tempfile
import json
import re
import fitz  # PyMuPDF
from openai import OpenAI
from langchain_community.document_loaders import DirectoryLoader
from policybuddy_cli import (
    generate_system_prompt, llm_generate_research_plan, llm_generate_pdf_search_queries,
    execute_pplx_search, generate_preliminary_report_from_perplexity, refine_research_plan_with_user_feedback,
    llm_generate_search_queries, execute_perplexity_queries_and_update_dict,
    llm_generate_pdf_search_queries_from_report, execute_google_pdf_search_queries_dict,
    enhance_preliminary_report_with_vector_search, 
    generate_markdown_from_enhanced_reports_json
)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize OpenAI and Perplexity clients
OPENAI_API_KEY = st.secrets["OPENAI_APIKey"]
PERPLEXITY_API_KEY = st.secrets["PERPLEXITY_APIKey"]
SERPER_API_KEY = st.secrets["SERPER_APIKey"]


openai_client = OpenAI(api_key=OPENAI_API_KEY)
perplexity_client = OpenAI(api_key=PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")


def fetch_and_store_pdf_locally(url):
    """
    Fetches a PDF from a URL and stores it locally in a temporary directory.
    Returns the local file path of the downloaded PDF.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred
        # Create a temporary directory if it doesn't already exist
        temp_dir = tempfile.gettempdir()
        pdf_name = url.split('/')[-1]
        local_pdf_path = os.path.join(temp_dir, pdf_name)
        with open(local_pdf_path, 'wb') as pdf_file:
            pdf_file.write(response.content)
        return local_pdf_path, None
    except requests.RequestException as e:
        return None, str(e)


def upload_pdf_to_supabase(local_pdf_path, bucket_name="supabasetestllm1"):
    """
    Uploads a PDF from a local file path to a specified Supabase Storage bucket.
    """
    pdf_name = os.path.basename(local_pdf_path)
    with open(local_pdf_path, "rb") as file_data:
        upload_response = supabase.storage().from_(bucket_name).upload(pdf_name, file_data)
        if upload_response.get('error') is None:
            public_url_response = supabase.storage().from_(bucket_name).get_public_url(pdf_name)
            return public_url_response.data.get('publicURL'), None
        else:
            return None, upload_response['error']['message']
        

def process_pdfs(pdf_urls):
    """
    For each PDF URL, fetches and stores the PDF locally, then uploads it to Supabase.
    """
    for pdf_url in pdf_urls:
        # First, download the PDF and store it locally
        local_pdf_path, download_error = fetch_and_store_pdf_locally(pdf_url)
        if local_pdf_path:
            st.write(f"PDF stored locally at: {local_pdf_path}")
            # Then, upload the locally stored PDF to Supabase
            public_url, upload_error = upload_pdf_to_supabase(local_pdf_path, "supabasetestllm1")
            if public_url:
                st.success(f"PDF uploaded to Supabase: {public_url}")
                # Placeholder for further processing using local PDF path or Supabase public URL
            else:
                st.error(f"Failed to upload PDF to Supabase: {upload_error}")
        else:
            st.error(f"Failed to download PDF: {download_error}")

def collect_user_context():
    st.subheader("Please provide your user context")
    user_context = {}
    
    # Text inputs for simple string responses
    user_context['user_job'] = st.text_input("What is your job role? (e.g., Policy Analyst, Sustainability Consultant, Due Diligence Expert)", "Policy Analyst")
    user_context['user_workplace'] = st.text_area("Where are you working? Be more descriptive of your organization's role. Do not input the organization's name specifically, for privacy purposes.", "A global NGO focused on environmental advocacy")
    user_context['report_audience'] = st.text_input("Who is this report meant for?", "Internal stakeholders")
    user_context['report_inspiration'] = st.text_input("What types of reports inspire you?", "IPCC Assessment Reports")
    user_context['sources_focus_search'] = st.text_input("What kind of sources would you like to focus on? (e.g., Multilateral Sources, Government Sources, Central Bank Reports)", "Multilateral Sources (IMF, ADB, World Bank, GGGI), Government Reports, Central Bank Reports")
    user_context['sources_date_focus_search'] = st.text_input("What year/date period do you want the search to be focused on?", "2020-2024")

    # Selectbox for predefined options
    output_types = ["Memo", "Report", "Policy Brief", "Landscape Analysis", "Research Paper", "Other"]
    user_context['desired_output_type'] = st.selectbox("What type of output are you looking to produce?", output_types, index=1)  # Default to "Report"
    
    sectors = ["Carbon Markets", "Renewable Energy", "Sustainable Agriculture", "Climate Finance", "Biodiversity", "Other"]
    selected_sector = st.selectbox("Select your sector of interest.", sectors, index=1)  # Default to "Renewable Energy"
    user_context['sector_of_interest'] = selected_sector
    
    # Dynamic text input based on the sector of interest
    user_context['topic_of_interest'] = st.text_input(f"Specify your topic of interest within {selected_sector}.", f"Impact of {selected_sector.lower()} on local ecosystems")
    
    # Text areas for longer inputs
    user_context['existing_knowledge'] = st.text_area("What do you already know? (Less than 200 words)", "N/A")
    user_context['knowledge_gaps'] = st.text_area("What would you like to know more about? (Less than 200 words)", "N/A")

    return user_context

def main():
    st.title("Research Assistant")

    user_context = collect_user_context()

    if st.button("Generate Research Plan"):
        # Generate system prompt and research plan
        system_prompt = generate_system_prompt(user_context)
        research_plan = llm_generate_research_plan(system_prompt, user_context['desired_output_type'], user_context['report_inspiration'])
        final_plan = refine_research_plan_with_user_feedback(system_prompt, research_plan)
        search_queries_dict = llm_generate_search_queries(final_plan)
        search_queries_dict_with_results = execute_perplexity_queries_and_update_dict(search_queries_dict)
        
        
        preliminary_report = generate_preliminary_report_from_perplexity(research_plan, search_queries_dict_with_results)

        #  Generate PDF search queries from the preliminary report
        google_pdf_search_queries = llm_generate_pdf_search_queries_from_report(preliminary_report)
        pdf_search_results, pdf_destination_folder = execute_google_pdf_search_queries_dict(google_pdf_search_queries)
        
        
            # Setup a temporary directory for local storage of PDFs
        with tempfile.TemporaryDirectory() as pdf_destination_folder:
            for pdf_url in pdf_search_results:
                # Download and save the PDF locally
                response = requests.get(pdf_url)
                if response.status_code == 200:
                    pdf_name = pdf_url.split('/')[-1]
                    local_pdf_path = os.path.join(pdf_destination_folder, pdf_name)
                    with open(local_pdf_path, 'wb') as pdf_file:
                        pdf_file.write(response.content)
                    st.write(f"PDF saved locally for processing: {local_pdf_path}")

                    # Then, upload the PDF from the local path to Supabase
                    public_url, error = upload_pdf_to_supabase(local_pdf_path, "supabasetestllm1")
                    if public_url:
                        st.write(f"PDF uploaded to Supabase: {public_url}")
                        # Now, you can further process the PDF using the local path or the Supabase public URL
                    else:
                        st.error(f"Failed to upload PDF: {error}")
                else:
                    st.error(f"Failed to fetch PDF from URL: {pdf_url}")
            st.write("Loading PDFs into OpenAI... Please wait...")
            loader = DirectoryLoader(pdf_destination_folder, show_progress=True, use_multithreading=True, silent_errors=True)
            pages = loader.load_and_split()

            # Assuming OpenAIEmbeddings is adjusted for Streamlit
            embeddings_instance = OpenAIEmbeddings()
            db = FAISS.from_documents(pages, embeddings_instance)
            
            # Save or display results
            # For demonstration, we display the count of processed pages
            st.write(f"Processed {len(pages)} pages into embeddings.")

        # Process the PDFs found by the search queries
        # This could involve downloading the PDFs, extracting information, and more
        # Implementation details depend on your application's needs and capabilities

        # Assuming PDF processing results in an enhanced report
            enhanced_reports = enhance_preliminary_report_with_vector_search(preliminary_report, db)
        
        # Generate the final markdown report
            markdown_report = generate_markdown_from_enhanced_reports_json(enhanced_reports, research_plan)
            st.markdown(markdown_report, unsafe_allow_html=True)
        
        # Provide a download button for the markdown report
            st.download_button(
                label="Download Markdown Report",
                data=markdown_report.encode(),
                file_name="markdown_report.md",
                mime="text/markdown"
            )



if __name__ == "__main__":
    main()

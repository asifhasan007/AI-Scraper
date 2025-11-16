import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import csv
from datetime import datetime
import io  


def decode_cloudflare_email(encoded_email):
    try:
        key = int(encoded_email[:2], 16)
        decoded = ''
        for i in range(2, len(encoded_email), 2):
            char_code = int(encoded_email[i:i+2], 16)
            decoded += chr(char_code ^ key)
        return decoded
    except Exception as e:
       
        st.error(f"Error decoding email: {e}")
        return None

def scrape_website(url):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    st.info(f"Scraping: {url}") 
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        
        protected_emails = []
        cf_email_tags = soup.find_all('a', class_='__cf_email__')
        
        if cf_email_tags:
            for tag in cf_email_tags:
                encoded = tag.get('data-cfemail')
                if encoded:
                    decoded_email = decode_cloudflare_email(encoded)
                    if decoded_email:
                        protected_emails.append(decoded_email)
                        tag.string = decoded_email

        
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'meta', 'link']):
            tag.decompose()
        
       
        text = soup.get_text(separator=' ', strip=True)
        
        return {
            'url': response.url,
            'title': soup.title.string if soup.title else 'No title',
            'text': text,
            'protected_emails': protected_emails
        }

    except requests.exceptions.RequestException as e:
        st.error(f"Error scraping website: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None

def extract_contacts_with_ai(scraped_data, api_key):
    if not scraped_data:
        return None
    
    st.info("Analyzing with Gemini AI...")
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        text = scraped_data['text']
        
        prompt = f"""You are a precise data extraction assistant. Extract contact information from the text below.

TEXT TO ANALYZE:
---
{text}
---

TASK: Extract contact information that is EXPLICITLY present in the text above.

RULES:
1. ONLY extract information that appears in the text
2. Do NOT make up or guess any data
3. If something is not found, use empty string "" or empty array []
4. Verify each piece of data exists before including it

Return ONLY a JSON object (no markdown, no explanations):
{{
 "company_name": "",
 "emails": [],
 "phones": [],
 "address": "",
 "website": "",
 "facebook": "",
 "twitter": "",
 "linkedin": "",
 "instagram": "",
 "business_hours": "",
 "description": ""
}}"""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.1)
        )
        
        result_text = response.text.strip()
        
       
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        contacts = json.loads(result_text)
        
        
        if scraped_data['protected_emails']:
            contacts['emails'].extend(scraped_data['protected_emails'])
            contacts['emails'] = list(set(contacts['emails']))
        
        contacts['url'] = scraped_data['url']
        contacts['title'] = scraped_data['title']
        
        return contacts
        
    except json.JSONDecodeError as e:
        st.error(f"AI response parsing error: {e}")
        st.code(f"Response: {response.text[:500]}") 
        return None
    except Exception as e:
        st.error(f"AI extraction error: {e}")
        return None



def display_results_st(contacts):
    if not contacts:
        st.warning("No data to display")
        return
    
    st.divider()
    st.subheader("📊 Contact Information Extracted")
    
    st.write(f"**URL:** {contacts.get('url', 'N/A')}")
    st.write(f"**Title:** {contacts.get('title', 'N/A')}")
    
    if contacts.get('company_name'):
        st.write(f"**Company:** {contacts['company_name']}")
    
    st.write(f"**Emails ({len(contacts.get('emails', []))}):**")
    if contacts.get('emails'):
        for email in contacts['emails']:
            st.write(f"  • {email}")
    else:
        st.write("  *No emails found*")
    
    st.write(f"**📞 Phone Numbers ({len(contacts.get('phones', []))}):**")
    if contacts.get('phones'):
        for phone in contacts['phones']:
            st.write(f"  • {phone}")
    else:
        st.write("  *No phone numbers found*")
    
    if contacts.get('address'):
        st.write(f"**Address:**\n  {contacts['address']}")
    
    if contacts.get('website'):
        st.write(f"**Website:** {contacts['website']}")
    
    st.write("**Social Media:**")
    socials = [
        ('Facebook', contacts.get('facebook', '')),
        ('Twitter', contacts.get('twitter', '')),
        ('LinkedIn', contacts.get('linkedin', '')),
        ('Instagram', contacts.get('instagram', ''))
    ]
    found_any_social = any(link for _, link in socials)
    if found_any_social:
        for platform, link in socials:
            if link:
                st.write(f"  • {platform}: {link}")
    else:
        st.write("  *No social media links found*")
    
    if contacts.get('business_hours'):
        st.write(f"**Business Hours:**\n  {contacts['business_hours']}")
    
    if contacts.get('description'):
        st.write(f"**Description:**\n  {contacts['description'][:200]}...")

def convert_to_csv(contacts):
    if not contacts:
        return None
    
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    
    writer.writerow(['Field', 'Value'])
    writer.writerow(['URL', contacts.get('url', 'N/A')])
    writer.writerow(['Title', contacts.get('title', 'N/A')])
    writer.writerow(['Company Name', contacts.get('company_name', 'N/A')])
    writer.writerow(['Emails', ', '.join(contacts.get('emails', [])) or 'N/A'])
    writer.writerow(['Phones', ', '.join(contacts.get('phones', [])) or 'N/A'])
    writer.writerow(['Address', contacts.get('address', 'N/A')])
    writer.writerow(['Website', contacts.get('website', 'N/A')])
    writer.writerow(['Facebook', contacts.get('facebook', 'N/A')])
    writer.writerow(['Twitter', contacts.get('twitter', 'N/A')])
    writer.writerow(['LinkedIn', contacts.get('linkedin', 'N/A')])
    writer.writerow(['Instagram', contacts.get('instagram', 'N/A')])
    writer.writerow(['Business Hours', contacts.get('business_hours', 'N/A')])
    writer.writerow(['Description', contacts.get('description', 'N/A')])
    
   
    return output.getvalue()



def main_app():
    st.set_page_config(page_title="AI Contact Scraper", layout="wide")
    st.title("🤖 AI-Powered Contact Scraper")
    
   
    api_key = st.secrets.get("GEMINI_API_KEY")
    
    if not api_key:
        st.error("🚨 GEMINI_API_KEY not found! Please add it to your .streamlit/secrets.toml file.")
        st.stop()
        
    
    url = st.text_input("Enter website URL to scrape:", placeholder="e.g., example.com")

    
    if st.button("Extract Contacts", type="primary"):
        if not url:
            st.warning("Please enter a URL above.")
        else:
            
            scraped_data = scrape_website(url)
            
            if scraped_data:
                st.success("Scraping complete!")
                
               
                contacts = extract_contacts_with_ai(scraped_data, api_key)
                
                if contacts:
                    st.success("AI extraction complete!")
                    
                    
                    display_results_st(contacts)
                    
                   
                    csv_data = convert_to_csv(contacts)
                    
                    if csv_data:
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"contacts_{timestamp}.csv"
                        
            
                        st.download_button(
                            label="Download Results as CSV",
                            data=csv_data,
                            file_name=filename,
                            mime='text/csv',
                        )
                else:
                    st.error("AI extraction failed.")
            else:
                st.error("Scraping failed. Check the URL and try again.")

if __name__ == "__main__":
    main_app()
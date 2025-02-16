import os
import json
import asyncio
import re
import requests
import threading
import time
import webbrowser
import numpy as np
import pandas as pd
import logging
import iris  # ✅ Vector database
from flask import Flask, request, jsonify
from urllib.parse import urljoin
from asgiref.sync import async_to_sync
from playwright.async_api import async_playwright
from mistralai import Mistral
from scrapybara import Scrapybara
from scrapybara.tools import BashTool, ComputerTool, EditTool
from scrapybara.anthropic import Anthropic
from scrapybara.prompts import UBUNTU_SYSTEM_PROMPT
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from sklearn.feature_extraction.text import TfidfVectorizer
from dain import Dain

# ✅ Initialize Dain for managing services
dain = Dain()

# ✅ Initialize API Clients
mistral_client = Mistral(api_key="secret")
scrapybara_client = Scrapybara(api_key="secret")

app = Flask(__name__)

# ✅ Logging Setup
logging.basicConfig(level=logging.INFO)

# ✅ Vector Database Service
class VectorDatabaseService:
    def __init__(self):
        self.cursor, self.table_name = self.create_table()

    def create_table(self):
        """Creates a new table for storing modified websites"""
        hostname = os.getenv('IRIS_HOSTNAME', 'localhost')
        CONNECTION_STRING = f"{hostname}:1972/USER"
        conn = iris.connect(CONNECTION_STRING, "demo", "demo")
        cursor = conn.cursor()
        table_name = "WebsiteMods"

        try:
            cursor.execute(f"DROP TABLE {table_name}")  # Reset table
        except:
            pass
        cursor.execute(f"CREATE TABLE {table_name} (oldSite TEXT, newSite TEXT)")
        return cursor, table_name

    def add_to_table(self, old_site, new_site):
        sql = f"INSERT INTO {self.table_name} (oldSite, newSite) VALUES (?, ?)"
        self.cursor.execute(sql, (old_site, new_site))

    def find_similar(self, input_site):
        """Finds a similar site modification using cosine similarity"""
        self.cursor.execute(f"SELECT * FROM {self.table_name}")
        fetched_data = self.cursor.fetchall()

        highest_score = 0
        best_match = None
        vectorizer = TfidfVectorizer()

        for old_site, new_site in fetched_data:
            vector1 = vectorizer.fit_transform([input_site]).toarray()
            vector2 = vectorizer.fit_transform([old_site]).toarray()
            similarity = np.dot(vector1, vector2.T) / (np.linalg.norm(vector1) * np.linalg.norm(vector2))
            
            if similarity > highest_score:
                highest_score = similarity
                best_match = new_site

        return best_match if highest_score > 0.8 else None  # Apply if similarity > 80%

# ✅ Web Scraper Service
class WebScraperService:
    async def scrape_async(self, url):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            content = await page.content()
            await browser.close()
        return content

    def scrape(self, url):
        return asyncio.run(self.scrape_async(url))

# ✅ AI Modifier Service
class AIModifierService:
    def modify(self, content, user_request):
        prompt = f"""
        The user wants to improve a webpage.
        Request: "{user_request}"
        Given the following HTML: {content}
        Generate an improved HTML page with better accessibility.
        """

        try:
            response = mistral_client.fim.complete(
                model="codestral-latest",
                prompt=prompt,
                suffix="applyModifications();",
                temperature=0,
                top_p=1,
            )
            return response.choices[0].message.content.strip() if response.choices else None
        except Exception as e:
            logging.error(f"🚨 AI modification failed: {e}")
            return None

# ✅ Scrapybara Automation Service
class ScrapybaraService:
    def click_first_link(self, url):
        instance = scrapybara_client.start_ubuntu(timeout_hours=0.1)
        time.sleep(3)  # Ensure Scrapybara is ready

        stream_url = instance.get_stream_url().stream_url
        if not stream_url:
            logging.error("❌ Scrapybara stream URL is empty!")
            return None

        webbrowser.open(stream_url)

        response = scrapybara_client.act(
            model=Anthropic(),
            tools=[BashTool(instance), ComputerTool(instance), EditTool(instance)],
            system=UBUNTU_SYSTEM_PROMPT,
            prompt=f"Open {url}, click the first link, and keep the browser open.",
        )

        return response

# ✅ Speech Generation Service (Eleven Labs)
class SpeechService:
    def generate_speech(self, text):
        ELEVEN_LABS_API_KEY = "secret"
        ELEVEN_LABS_VOICE_ID = "secret"

        client = ElevenLabs(api_key=ELEVEN_LABS_API_KEY)
        audio = client.text_to_speech.convert(
            text=text, voice_id=ELEVEN_LABS_VOICE_ID, model_id="eleven_multilingual_v2", output_format="mp3_44100_128"
        )
        play(audio)

# ✅ Dain-Based Handler Logic
class WebsiteModificationHandler:
    def __init__(self):
        self.vector_db = VectorDatabaseService()
        self.scraper = WebScraperService()
        self.ai_modifier = AIModifierService()
        self.scrapybara = ScrapybaraService()
        self.speech = SpeechService()

    def handle_request(self, url, user_request):
        try:
            original_content = self.scraper.scrape(url)
            if not original_content:
                return {"error": "Failed to scrape website"}

            # ✅ Check for similar modification in vector DB
            existing_modification = self.vector_db.find_similar(original_content)
            if existing_modification:
                logging.info("✅ Found similar modification in database.")
                return {"html": existing_modification}

            # ✅ If user requests link-clicking, use Scrapybara
            if "click on the link" in user_request.lower():
                self.scrapybara.click_first_link(url)
                return {"message": "Scrapybara is running."}

            # ✅ Modify website with AI
            modified_content = self.ai_modifier.modify(original_content, user_request)
            if not modified_content:
                return {"error": "AI modification failed"}

            # ✅ Store in vector DB
            self.vector_db.add_to_table(original_content, modified_content)

            # ✅ Handle "read this to me" requests
            if "read this to me" in user_request.lower():
                extracted_text = re.sub(r"<[^>]+>", "", modified_content)  # Strip HTML tags
                self.speech.generate_speech(extracted_text)
                return {"message": "Playing audio..."}

            return {"html": modified_content}

        except Exception as e:
            logging.error(f"❌ Error handling request: {e}")
            return {"error": str(e)}

# ✅ Initialize Handler
handler = WebsiteModificationHandler()

# ✅ Flask API Route
@app.route("/modify", methods=["POST"])
def modify_website():
    data = request.json
    return jsonify(handler.handle_request(data.get("url"), data.get("changes")))

# ✅ Run Flask Server
if __name__ == "__main__":
    app.run(port=8000, debug=True)

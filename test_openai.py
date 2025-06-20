# test_openai.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("OPENAI_API_KEY not found in environment variables.")
else:
    try:
        client = OpenAI(api_key=API_KEY)
        print("OpenAI client initialized. Attempting a test call...")
        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"}
            ]
        )
        print("API Call Successful!")
        print("Response:", chat_completion.choices[0].message.content)
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Ensure your API key is correct and billing is set up on platform.openai.com.")
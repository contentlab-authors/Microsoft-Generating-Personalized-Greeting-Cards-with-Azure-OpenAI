import os
import time
import random
from threading import Thread

import httpx
import requests

from CustomHTTPTransport import CustomHTTPTransport
from flask import Flask, render_template, request
from fuzzywuzzy import process
from openai import AzureOpenAI
from PIL import Image, ImageDraw, ImageFont

# Constants and Configurations
OPENAI_API_KEY = '<KEY_YOU_SAVED_IN_STEP_1>'
API_VERSION = "2023-12-01-preview"
AZURE_ENDPOINT = f'https://<ENDPOINT_YOU_SAVED_IN_STEP_1>/openai/deployments/Dalle3/images/generations?api-version={API_VERSION}'
FONT_PATH = "static/fonts/AmaticSC-Bold.ttf"

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def is_keyword_present(user_input, keyword, threshold=95):
    words = user_input.lower().split()
    match = process.extractOne(keyword, words)
    return match and match[1] >= threshold

def create_dalle_prompt(user_input):
    base_prompt = "Draw or paint a 2D printable illustration for the front of a visually appealing greeting card"
    default_enhancement = " that is elegant with harmonious colors and balanced composition"
    additional_instructions = ". DO NOT use any made-up words."
    thematic_enhancement = ""

    # Dictionary for thematic enhancements
    enhancements = {
        "birthday": " with birthday themes like balloons, cake, and gifts",
        "congratulations": " with celebratory motifs like fireworks, champagne, and congratulatory banners"
    }

    # Check for thematic keywords
    for keyword, enhancement in enhancements.items():
        if is_keyword_present(user_input, keyword):
            thematic_enhancement = enhancement
            break

    return f"{base_prompt}{thematic_enhancement or default_enhancement} basing what you draw on the phrase: '{user_input}'{additional_instructions}"


def download_image(image_url, filename):
    image_content = requests.get(image_url).content
    with open(filename, "wb") as image_file:
        image_file.write(image_content)

def add_footer_to_image(original_image_path, text):
    with Image.open(original_image_path) as img:
        new_height = img.height + 200
        new_img = Image.new("RGB", (img.width, new_height), "white")
        new_img.paste(img, (0, 0))
        draw = ImageDraw.Draw(new_img)
        font = get_dynamic_font_size(draw, img.width, text)
        text_x, text_y = calculate_text_position(draw, img, text, font)
        draw.text((text_x, text_y), text, fill="black", font=font)

        # Extract directory and filename
        directory, filename = os.path.split(original_image_path)
        modified_image_path = os.path.join(directory, f"modified_{filename}")
        new_img.save(modified_image_path)
        return modified_image_path

def get_dynamic_font_size(draw, image_width, text):
    max_font_size = 100
    font = ImageFont.truetype(FONT_PATH, max_font_size)
    text_width, _ = draw.textbbox((0, 0), text, font=font)[2:]
    while text_width > image_width and max_font_size > 1:
        max_font_size -= 1
        font = ImageFont.truetype(FONT_PATH, max_font_size)
        text_width, _ = draw.textbbox((0, 0), text, font=font)[2:]
    return font

def calculate_text_position(draw, img, text, font):
    text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:]
    text_x = (img.width - text_width) / 2
    text_y = img.height + (200 - text_height) / 2
    return text_x, text_y

def generate_image_with_dalle(prompt, index, user_input):
    # Azure OpenAI Client Initialization
    client = AzureOpenAI(
        api_key=OPENAI_API_KEY,
        azure_endpoint=AZURE_ENDPOINT,
        api_version=API_VERSION,
        http_client=httpx.Client(transport=CustomHTTPTransport())
    )
    final_prompt = create_dalle_prompt(prompt)
    generation_response = client.images.generate(prompt=final_prompt, model="dall-e-3", quality='standard', style='vivid', size='1024x1024', n=1)
    image_url = generation_response.data[0].url

    unique_filename = f"generated_image_{index}_{int(time.time())}_{random.randint(1000, 9999)}.png"
    image_path = os.path.join('static', unique_filename)
    download_image(image_url, image_path)
    
    modified_image_path = add_footer_to_image(image_path, user_input)
    return os.path.basename(modified_image_path)

def generate_images_in_parallel(prompts, user_input):
    threads = []
    image_filenames = []
    for i, prompt in enumerate(prompts):
        thread = Thread(target=lambda q, arg1, arg2: q.append(generate_image_with_dalle(arg1, i, arg2)), args=(image_filenames, prompt, user_input))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    return image_filenames

@app.route('/generate_card', methods=['POST'])
def generate_card():
    user_message = request.form['message']
    prompts = [f"{user_message}" for i in range(0, 3)]
    image_filenames = generate_images_in_parallel(prompts, user_message)
    return render_template('card.html', message=user_message, image_paths=image_filenames)

if __name__ == '__main__':
     app.run(debug=True)
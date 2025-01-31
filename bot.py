import logging
import os
import queue
import threading
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from pytube import YouTube
import ffmpeg
from flask import Flask, request
import json

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Your bot's API token
TELEGRAM_API_TOKEN = '7750424717:AAFTjX9bFRYP2kR6WMDGIYO_zEgsDgT2puQ'

# Path to store the downloaded files
DOWNLOAD_FOLDER = 'downloads/'

# Ensure the download folder exists
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Queue to store song requests
song_queue = queue.Queue()

# Function to download the audio using pytube
def download_audio(search_query):
    yt = YouTube(f'https://www.youtube.com/results?search_query={search_query}')
    stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()

    # Download the audio
    audio_file = os.path.join(DOWNLOAD_FOLDER, f'{search_query}.mp4')
    stream.download(output_path=DOWNLOAD_FOLDER, filename=f'{search_query}.mp4')

    # Convert the mp4 to mp3 using ffmpeg
    mp3_file = os.path.join(DOWNLOAD_FOLDER, f'{search_query}.mp3')
    ffmpeg.input(audio_file).output(mp3_file).run()

    # Clean up the mp4 file after conversion
    os.remove(audio_file)

    return mp3_file

# Function to process the queue
def process_queue():
    while True:
        if not song_queue.empty():
            song_request = song_queue.get()

            # Notify the user that the song is being processed
            try:
                audio_file = download_audio(song_request['song_name'])

                # Send the audio file back to the user
                with open(audio_file, 'rb') as audio:
                    song_request['context'].bot.send_audio(song_request['user_id'], audio=audio)

                # Clean up the downloaded audio file
                os.remove(audio_file)

                # Notify the user that the song is ready
                song_request['context'].bot.send_message(song_request['user_id'], f"Your song '{song_request['song_name']}' has been delivered!")
            
            except Exception as e:
                logger.error(f"Error while downloading song: {e}")
                song_request['context'].bot.send_message(song_request['user_id'], f"An error occurred while processing your song '{song_request['song_name']}'.")

            song_queue.task_done()

# Flask Setup
app = Flask(__name__)

@app.route(f'/{TELEGRAM_API_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), updater.bot)
    dispatcher.process_update(update)
    return 'OK', 200

@app.route('/')
def index():
    return "Hello, this is your Music Bot!"

# Start command for the bot
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Welcome to the Music Bot! Just send the name of the song you want to listen to.")

# Function to handle song requests
def get_song(update: Update, context: CallbackContext) -> None:
    query = ' '.join(context.args)
    
    if not query:
        update.message.reply_text("Please provide a song name. Example: /play Never Gonna Give You Up")
        return
    
    update.message.reply_text(f"Searching for {query}...")

    # Add the song request to the queue
    song_queue.put({'song_name': query, 'user_id': update.message.chat_id, 'context': context})

    update.message.reply_text(f"Your song request for '{query}' has been added to the queue. Please wait...")

# Error handler
def error(update: Update, context: CallbackContext) -> None:
    logger.warning(f"Update {update} caused error {context.error}")

def main():
    # Set up the Updater and Dispatcher for the Telegram bot
    global updater, dispatcher
    updater = Updater(TELEGRAM_API_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Command Handlers for Telegram Bot
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("play", get_song))

    # Error Handler
    dispatcher.add_error_handler(error)

    # Set up the webhook for Flask
    updater.bot.set_webhook(url=f'https://web-38h7.onrender.com/{TELEGRAM_API_TOKEN}')

    # Start the Flask app
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))

if __name__ == '__main__':
    # Start a background thread to process the queue
    threading.Thread(target=process_queue, daemon=True).start()
    main()

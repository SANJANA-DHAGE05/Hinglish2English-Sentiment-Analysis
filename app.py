# Required libraries
import os
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename

import nltk
nltk.download('punkt')
from nltk.tokenize import word_tokenize

from googletrans import Translator
import idiomcorpus
import enchant
import sqlite3
from sqlite3 import Error

# Add TextBlob for sentiment analysis
from textblob import TextBlob

# Plotly for visualization
import plotly
import plotly.graph_objs as go
import json

# Initialize dictionary and translator
d = enchant.Dict("en_US")
translator = Translator()

# Initialize the Flask application
app = Flask(__name__, template_folder='template/HTML')

# Configuration
UPLOAD_FOLDER = os.path.dirname(os.path.abspath(__file__))
ALLOWED_EXTENSIONS = {'txt'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.urandom(24)  # More secure secret key generation

# Global variables
text1 = []
text2 = []
file_content = ""
filename = ""
result = ''
sentiment_result = ''

# Database path
DATABASE_PATH = "Database.db"  # Path to the uploaded database


#generate sentiment-chart
def generate_sentiment_chart(text, polarity):
    # Tokenize the text and analyze sentiment of each word
    words = text.split()
    total_words = len(words)
    
    # Sentiment analysis for each word
    word_sentiments = [TextBlob(word).sentiment.polarity for word in words]
    
    # Categorize words
    negative_words = [word for word, sent in zip(words, word_sentiments) if sent < -0.05]
    neutral_words = [word for word, sent in zip(words, word_sentiments) if -0.05 <= sent <= 0.05]
    positive_words = [word for word, sent in zip(words, word_sentiments) if sent > 0.05]
    
    # Calculate percentages
    negative_percent = len(negative_words) / total_words * 100
    neutral_percent = len(neutral_words) / total_words * 100
    positive_percent = len(positive_words) / total_words * 100
    
    # Prepare data for the chart
    categories = ['Negative', 'Neutral', 'Positive']
    
    # Determine the sentiment type and create bar values
    if polarity < -0.05:  # Negative sentiment
        bar_values = [negative_percent, neutral_percent, positive_percent]
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
        hover_text = [
            f'Negative Words: {len(negative_words)}<br>Percentage: {negative_percent:.2f}%<br>Words: {", ".join(negative_words[:5])}{"..." if len(negative_words) > 5 else ""}',
            f'Neutral Words: {len(neutral_words)}<br>Percentage: {neutral_percent:.2f}%<br>Words: {", ".join(neutral_words[:5])}{"..." if len(neutral_words) > 5 else ""}',
            f'Positive Words: {len(positive_words)}<br>Percentage: {positive_percent:.2f}%<br>Words: {", ".join(positive_words[:5])}{"..." if len(positive_words) > 5 else ""}'
        ]
    elif polarity > 0.05:  # Positive sentiment
        bar_values = [negative_percent, neutral_percent, positive_percent]
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
        hover_text = [
            f'Negative Words: {len(negative_words)}<br>Percentage: {negative_percent:.2f}%<br>Words: {", ".join(negative_words[:5])}{"..." if len(negative_words) > 5 else ""}',
            f'Neutral Words: {len(neutral_words)}<br>Percentage: {neutral_percent:.2f}%<br>Words: {", ".join(neutral_words[:5])}{"..." if len(neutral_words) > 5 else ""}',
            f'Positive Words: {len(positive_words)}<br>Percentage: {positive_percent:.2f}%<br>Words: {", ".join(positive_words[:5])}{"..." if len(positive_words) > 5 else ""}'
        ]
    else:  # Neutral sentiment
        bar_values = [negative_percent, neutral_percent, positive_percent]
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
        hover_text = [
            f'Negative Words: {len(negative_words)}<br>Percentage: {negative_percent:.2f}%<br>Words: {", ".join(negative_words[:5])}{"..." if len(negative_words) > 5 else ""}',
            f'Neutral Words: {len(neutral_words)}<br>Percentage: {neutral_percent:.2f}%<br>Words: {", ".join(neutral_words[:5])}{"..." if len(neutral_words) > 5 else ""}',
            f'Positive Words: {len(positive_words)}<br>Percentage: {positive_percent:.2f}%<br>Words: {", ".join(positive_words[:5])}{"..." if len(positive_words) > 5 else ""}'
        ]
    
    # Create Plotly bar chart
    fig = go.Figure(data=[
        go.Bar(
            x=categories, 
            y=bar_values, 
            marker_color=colors,
            text=[f'{val:.2f}%' for val in bar_values],
            textposition='auto',
            hovertext=hover_text,
            hoverinfo='text'
        )
    ])
    
    # Customize layout
    fig.update_layout(
        title='Sentiment Analysis Breakdown',
        xaxis_title='Sentiment Categories',
        yaxis_title='Percentage of Words',
        height=500,
        width=500,
        template='plotly_white'
    )
    
    # Convert to JSON for rendering
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON

def analyze_sentiment(text):
    blob = TextBlob(text)
    
    # Determine sentiment based on polarity with three categories
    polarity = blob.sentiment.polarity
    
    if polarity > 0.05:
        sentiment = 'Positive'
        emoji = '😄'  # Smiling face
    elif polarity < -0.05:
        sentiment = 'Negative'
        emoji = '😞'  # Sad face
    else:
        sentiment = 'Neutral'
        emoji = '😐'  # Neutral face
    
    return {
        'sentiment': sentiment,
        'polarity': round(polarity, 2),
        'emoji': emoji
    }

def allowed_file(filename):
    """
    Utility function to check allowed file extensions
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def connection(db_file):
    """
    Define connection function which will connect to database 
    """
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(f"Database Opening Error: {e}")
        return None

def fetch_notations(rtext):
    """
    Fetch long notation for the given text (case-insensitively) from the database.
    """
    try:
        conn = connection(DATABASE_PATH)
        if conn:
            with conn:
                cur = conn.cursor()
                # Convert text to lowercase for consistent matching
                normalized_text = rtext.lower()
                cur.execute("SELECT Long_Notations FROM Keys WHERE LOWER(Short_Notations) = ?", (normalized_text,))
                row = cur.fetchone()
                if row:
                    return row[0]  # Return the long notation if found
                else:
                    return rtext  # Return the original text if not found
    except Error as e:
        print(f"Database fetch error: {e}")
        return rtext

def perform_operation():
    """
    Perform idiom conversion
    """
    global result
    try:
        object = idiomcorpus.Idiomcorpus()
        object.idiom_init(result)
        object.check_idiom()
        object.idiom_convert()
        return object.idiom_display()
    except Exception as e:
        print(f"Idiom conversion error: {e}")
        return result

def google_translate(text):
    """
    Translate text using Google Translator
    """
    try:
        translation = translator.translate(text, dest='en')
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def conversion_fun(input_txt):
    """
    Convert input text to English
    """
    global result
    global text1
    global text2
    
    text1 = []
    text2 = []
    
    translated_text = google_translate(input_txt)
    token = word_tokenize(translated_text)
    
    for i in token:
        long_notation = fetch_notations(i)
        text1.append(long_notation)

    ft = " ".join(text1)
    token = word_tokenize(ft)

    for i in token:
        text2.append(i if d.check(i) else i)

    ft = " ".join(text2)
    result = ft
    
    return perform_operation()

# Root page of the application (landing page)
@app.route("/", methods=['GET']) 
def index_page():
    return render_template("index.html")

# Home page route
@app.route("/home", methods=['GET', 'POST']) 
def home_page():
    return render_template("home_page.html")

@app.route('/home')
def home():
    return render_template('home_page.html')



#radio 
@app.route("/radio_check", methods=['POST'])
def radio_check():
    """
    Check for the input method and process accordingly
    """
    global result
    global text1
    global text2 
    global sentiment_result
    
    option1 = request.form.get('radiobtn')
    
    try:
        if option1 == '1':  # Keyboard input
            a = keyboard_ip()
        elif option1 == '2':  # Voice input
            t = request.form.get('text3', '')
            a = conversion_fun(t)
        elif option1 == '3':  # File input
            a = file_ip()
        else:
            return render_template("home_page.html", error="Invalid input method")
        
        # Perform sentiment analysis on the converted text
        sentiment_result = analyze_sentiment(a)
        
        # Generate sentiment chart (pass both text and polarity)
        sentiment_chart = generate_sentiment_chart(a, sentiment_result['polarity'])
        
        text1 = []
        text2 = []
        
        return render_template("home_page.html", 
                               etext=a, 
                               sentiment=sentiment_result['sentiment'], 
                               polarity=sentiment_result['polarity'],
                               emoji=sentiment_result['emoji'],
                               sentiment_chart=sentiment_chart)
    
    except Exception as e:
        print(f"Error in radio_check: {e}")
        return render_template("home_page.html", error="An error occurred during processing")
    
@app.route("/about_page")
def about_page():
    """Open about page"""
    return render_template("about_page.html")

@app.route("/help_page")
def help_page():
    """Open help page"""
    return render_template("help_page.html")

def keyboard_ip():
    """Take input through keyboard"""
    user_ip = request.form.get('hinglish', '')
    return conversion_fun(user_ip)

def file_ip():
    """Take file as input from the user"""
    global file_content
    
    if 'myfile' not in request.files:
        raise ValueError("No file part")
    
    file = request.files['myfile']
    
    if file.filename == '':
        raise ValueError("No selected file")
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            os.remove(file_path)
            return conversion_fun(file_content)
        except Exception as e:
            print(f"File reading error: {e}")
            raise
    else:
        raise ValueError("File type not allowed")

if __name__ == "__main__":
    app.run(debug=True)

    
# #  ------app.py-------

# # Required libraries
# import os
# from flask import Flask, request, render_template
# from werkzeug.utils import secure_filename

# import nltk
# nltk.download('punkt')
# from nltk.tokenize import word_tokenize

# from googletrans import Translator
# import idiomcorpus
# import enchant
# import sqlite3
# from sqlite3 import Error

# # Add TextBlob for sentiment analysis
# from textblob import TextBlob

# # Plotly for visualization
# import plotly
# import plotly.graph_objs as go
# import json

# # Initialize dictionary and translator
# d = enchant.Dict("en_US")
# translator = Translator()

# # Initialize the Flask application
# app = Flask(__name__, template_folder='template/HTML')

# # Configuration
# UPLOAD_FOLDER = os.path.dirname(os.path.abspath(__file__))
# ALLOWED_EXTENSIONS = {'txt'}

# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
# app.secret_key = os.urandom(24)  # More secure secret key generation

# # Global variables
# text1 = []
# text2 = []
# file_content = ""
# filename = ""
# result = ''
# sentiment_result = ''

# # Database path
# DATABASE_PATH = "Database.db"  # Path to the uploaded database

# def generate_sentiment_chart(polarity):
#     """
#     Generate a bar chart representing sentiment polarity.
    
#     Args:
#         polarity (float): The polarity score from sentiment analysis
    
#     Returns:
#         str: JSON-encoded Plotly chart
#     """
#     # Create bar chart data
#     categories = ['Negative', 'Neutral', 'Positive']
    
#     # Adjust bar heights based on polarity
#     if polarity < 0:
#         bar_values = [abs(polarity), 0, 0]
#     elif polarity > 0:
#         bar_values = [0, 0, polarity]
#     else:
#         bar_values = [0, abs(polarity), 0]
    
#     # Define color palette
#     colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    
#     # Create Plotly bar chart
#     fig = go.Figure(data=[
#         go.Bar(
#             x=categories, 
#             y=bar_values, 
#             marker_color=colors,
#             text=[f'{val:.2f}' for val in bar_values],
#             textposition='auto'
#         )
#     ])
    
#     # Customize layout
#     fig.update_layout(
#         title='Sentiment Polarity',
#         xaxis_title='Sentiment Categories',
#         yaxis_title='Polarity Score',
#         height=400,
#         width=500,
#         template='plotly_white'
#     )
    
#     # Convert to JSON for rendering
#     graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
#     return graphJSON

# def analyze_sentiment(text):
#     """
#     Analyze the sentiment of the given text.
#     Returns a sentiment classification and corresponding emoji.
#     """
#     blob = TextBlob(text)
    
#     # Determine sentiment based on polarity with three categories
#     polarity = blob.sentiment.polarity
    
#     if polarity > 0.05:
#         sentiment = 'Positive'
#         emoji = '😄'  # Smiling face
#     elif polarity < -0.05:
#         sentiment = 'Negative'
#         emoji = '😞'  # Sad face
#     else:
#         sentiment = 'Neutral'
#         emoji = '😐'  # Neutral face
    
#     return {
#         'sentiment': sentiment,
#         'polarity': round(polarity, 2),
#         'emoji': emoji
#     }

# def allowed_file(filename):
#     """
#     Utility function to check allowed file extensions
#     """
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def connection(db_file):
#     """
#     Define connection function which will connect to database 
#     """
#     try:
#         conn = sqlite3.connect(db_file)
#         return conn
#     except Error as e:
#         print(f"Database Opening Error: {e}")
#         return None

# def fetch_notations(rtext):
#     """
#     Fetch long notation for the given text (case-insensitively) from the database.
#     """
#     try:
#         conn = connection(DATABASE_PATH)
#         if conn:
#             with conn:
#                 cur = conn.cursor()
#                 # Convert text to lowercase for consistent matching
#                 normalized_text = rtext.lower()
#                 cur.execute("SELECT Long_Notations FROM Keys WHERE LOWER(Short_Notations) = ?", (normalized_text,))
#                 row = cur.fetchone()
#                 if row:
#                     return row[0]  # Return the long notation if found
#                 else:
#                     return rtext  # Return the original text if not found
#     except Error as e:
#         print(f"Database fetch error: {e}")
#         return rtext

# def perform_operation():
#     """
#     Perform idiom conversion
#     """
#     global result
#     try:
#         object = idiomcorpus.Idiomcorpus()
#         object.idiom_init(result)
#         object.check_idiom()
#         object.idiom_convert()
#         return object.idiom_display()
#     except Exception as e:
#         print(f"Idiom conversion error: {e}")
#         return result

# def google_translate(text):
#     """
#     Translate text using Google Translator
#     """
#     try:
#         translation = translator.translate(text, dest='en')
#         return translation.text
#     except Exception as e:
#         print(f"Translation error: {e}")
#         return text

# def conversion_fun(input_txt):
#     """
#     Convert input text to English
#     """
#     global result
#     global text1
#     global text2
    
#     text1 = []
#     text2 = []
    
#     translated_text = google_translate(input_txt)
#     token = word_tokenize(translated_text)
    
#     for i in token:
#         long_notation = fetch_notations(i)
#         text1.append(long_notation)

#     ft = " ".join(text1)
#     token = word_tokenize(ft)

#     for i in token:
#         text2.append(i if d.check(i) else i)

#     ft = " ".join(text2)
#     result = ft
    
#     return perform_operation()

# # Routes
# @app.route("/", methods=['GET']) 
# def index_page():
#     """Root page of the application (landing page)"""
#     return render_template("index.html")

# @app.route("/home", methods=['GET', 'POST']) 
# def home_page():
#     """Home page route"""
#     return render_template("home_page.html")

# @app.route("/radio_check", methods=['POST'])
# def radio_check():
#     """
#     Check for the input method and process accordingly
#     """
#     global result
#     global text1
#     global text2 
#     global sentiment_result
    
#     option1 = request.form.get('radiobtn')
    
#     try:
#         if option1 == '1':  # Keyboard input
#             a = keyboard_ip()
#         elif option1 == '2':  # Voice input
#             t = request.form.get('text3', '')
#             a = conversion_fun(t)
#         elif option1 == '3':  # File input
#             a = file_ip()
#         else:
#             return render_template("home_page.html", error="Invalid input method")
        
#         # Perform sentiment analysis on the converted text
#         sentiment_result = analyze_sentiment(a)
        
#         # Generate sentiment chart
#         sentiment_chart = generate_sentiment_chart(sentiment_result['polarity'])
        
#         text1 = []
#         text2 = []
        
#         return render_template("home_page.html", 
#                                etext=a, 
#                                sentiment=sentiment_result['sentiment'], 
#                                polarity=sentiment_result['polarity'],
#                                emoji=sentiment_result['emoji'],
#                                sentiment_chart=sentiment_chart)
    
#     except Exception as e:
#         print(f"Error in radio_check: {e}")
#         return render_template("home_page.html", error="An error occurred during processing")

# @app.route("/about_page")
# def about_page():
#     """Open about page"""
#     return render_template("about_page.html")

# @app.route("/help_page")
# def help_page():
#     """Open help page"""
#     return render_template("help_page.html")

# def keyboard_ip():
#     """Take input through keyboard"""
#     user_ip = request.form.get('hinglish', '')
#     return conversion_fun(user_ip)

# def file_ip():
#     """Take file as input from the user"""
#     global file_content
    
#     if 'myfile' not in request.files:
#         raise ValueError("No file part")
    
#     file = request.files['myfile']
    
#     if file.filename == '':
#         raise ValueError("No selected file")
    
#     if file and allowed_file(file.filename):
#         filename = secure_filename(file.filename)
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#         file.save(file_path)
        
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 file_content = f.read()
#             os.remove(file_path)
#             return conversion_fun(file_content)
#         except Exception as e:
#             print(f"File reading error: {e}")
#             raise
#     else:
#         raise ValueError("File type not allowed")

# if __name__ == "__main__":
#     app.run(debug=True)








# # ========== db short fetching =========
# # Required libraries
# import os
# from flask import Flask, request, render_template
# from werkzeug.utils import secure_filename

# import nltk
# nltk.download('punkt')
# from nltk.tokenize import word_tokenize

# from googletrans import Translator
# import idiomcorpus
# import enchant
# import sqlite3
# from sqlite3 import Error

# # Add TextBlob for sentiment analysis
# from textblob import TextBlob

# # Initialize dictionary and translator
# d = enchant.Dict("en_US")
# translator = Translator()

# # Configuration
# UPLOAD_FOLDER = os.path.dirname(os.path.abspath(__file__))
# ALLOWED_EXTENSIONS = {'txt'}

# # Initialize the Flask application
# app = Flask(__name__, template_folder='template/HTML')
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
# app.secret_key = os.urandom(24)  # More secure secret key generation

# # Global variables
# text1 = []
# text2 = []
# file_content = ""
# filename = ""
# result = ''
# sentiment_result = ''

# # Database path
# DATABASE_PATH = "Database.db"  # Path to the uploaded database

# # Enhanced Sentiment Analysis Function with Emojis
# def analyze_sentiment(text):
#     """
#     Analyze the sentiment of the given text.
#     Returns a sentiment classification and corresponding emoji.
#     """
#     blob = TextBlob(text)
    
#     # Determine sentiment based on polarity with simplified emoji selection
#     polarity = blob.sentiment.polarity
    
#     if polarity > 0.05:
#         sentiment = 'Positive'
#         emoji = '😄'  # Smiling face
#     elif -0.05 <= polarity <= 0.05:
#         sentiment = 'Neutral'
#         emoji = '😐'  # Neutral face
#     else:
#         sentiment = 'Negative'
#         emoji = '😞'  # Sad face
    
#     return {
#         'sentiment': sentiment,
#         'polarity': round(polarity, 2),
#         'emoji': emoji
#     }


# # Utility function to check allowed file extensions
# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# # Root page of the application (landing page)
# @app.route("/", methods=['GET']) 
# def index_page():
#     return render_template("index.html")

# # Home page route
# @app.route("/home", methods=['GET', 'POST']) 
# def home_page():
#     return render_template("home_page.html")

# @app.route('/home')
# def home():
#     return render_template('home_page.html')



# # Check for the input method 
# @app.route("/radio_check", methods=['POST'])
# def radio_check():
#     global result
#     global text1
#     global text2 
#     global sentiment_result
    
#     option1 = request.form.get('radiobtn')
    
#     try:
#         if option1 == '1':  # Keyboard input
#             a = keyboard_ip()
#         elif option1 == '2':  # Voice input
#             t = request.form.get('text3', '')
#             a = conversion_fun(t)
#         elif option1 == '3':  # File input
#             a = file_ip()
#         else:
#             return render_template("home_page.html", error="Invalid input method")
        
#         # Perform sentiment analysis on the converted text
#         sentiment_result = analyze_sentiment(a)
        
#         text1 = []
#         text2 = []
        
#         return render_template("home_page.html", 
#                                etext=a, 
#                                sentiment=sentiment_result['sentiment'], 
#                                polarity=sentiment_result['polarity'],
#                                emoji=sentiment_result['emoji'])
    
#     except Exception as e:
#         print(f"Error in radio_check: {e}")
#         return render_template("home_page.html", error="An error occurred during processing")

# # Open about page
# @app.route("/about_page")
# def about_page():
#     return render_template("about_page.html")

# # Open help page
# @app.route("/help_page")
# def help_page():
#     return render_template("help_page.html")

# # Take input through keyboard
# def keyboard_ip():
#     user_ip = request.form.get('hinglish', '')
#     return conversion_fun(user_ip)

# # Take file as input from the user
# def file_ip():
#     global file_content
    
#     if 'myfile' not in request.files:
#         raise ValueError("No file part")
    
#     file = request.files['myfile']
    
#     if file.filename == '':
#         raise ValueError("No selected file")
    
#     if file and allowed_file(file.filename):
#         filename = secure_filename(file.filename)
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#         file.save(file_path)
        
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 file_content = f.read()
#             os.remove(file_path)
#             return conversion_fun(file_content)
#         except Exception as e:
#             print(f"File reading error: {e}")
#             raise
#     else:
#         raise ValueError("File type not allowed")

# # Define connection function which will connect to database 
# def connection(db_file):
#     try:
#         conn = sqlite3.connect(db_file)
#         return conn
#     except Error as e:
#         print(f"Database Opening Error: {e}")
#         return None

# # Fetch short and long notations from the database, case-insensitively
# def fetch_notations(rtext):
#     """
#     Fetch long notation for the given text (case-insensitive) from the database.
#     """
#     try:
#         conn = connection(DATABASE_PATH)
#         if conn:
#             with conn:
#                 cur = conn.cursor()
#                 # Convert text to lowercase for consistent matching
#                 normalized_text = rtext.lower()
#                 cur.execute("SELECT Long_Notations FROM Keys WHERE LOWER(Short_Notations) = ?", (normalized_text,))
#                 row = cur.fetchone()
#                 if row:
#                     return row[0]  # Return the long notation if found
#                 else:
#                     return rtext  # Return the original text if not found
#     except Error as e:
#         print(f"Database fetch error: {e}")
#         return rtext

# # Perform idiom conversion
# def perform_operation():
#     global result
#     try:
#         object = idiomcorpus.Idiomcorpus()
#         object.idiom_init(result)
#         object.check_idiom()
#         object.idiom_convert()
#         return object.idiom_display()
#     except Exception as e:
#         print(f"Idiom conversion error: {e}")
#         return result

# # Translate text using Google Translator
# def google_translate(text):
#     try:
#         translation = translator.translate(text, dest='en')
#         return translation.text
#     except Exception as e:
#         print(f"Translation error: {e}")
#         return text

# # Convert input text to English
# def conversion_fun(input_txt):
#     global result
#     global text1
#     global text2
    
#     text1 = []
#     text2 = []
    
#     translated_text = google_translate(input_txt)
#     token = word_tokenize(translated_text)
    
#     for i in token:
#         long_notation = fetch_notations(i)
#         text1.append(long_notation)

#     ft = " ".join(text1)
#     token = word_tokenize(ft)

#     for i in token:
#         text2.append(i if d.check(i) else i)

#     ft = " ".join(text2)
#     result = ft
    
#     return perform_operation()

# if __name__ == "__main__":
#     app.run(debug=True)




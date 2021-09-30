from flask import Flask, jsonify, request
import nltk
from nltk.stem import WordNetLemmatizer
lemmatizer = WordNetLemmatizer()

import pickle
import numpy as np
from tensorflow.keras.models import load_model

import json
import random
from flask_cors import CORS

import os
from dotenv import load_dotenv

from pymongo import MongoClient
from bson import json_util
import pymongo

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def connect_db(connection_string,verbose=False):
  try:
     
    client = MongoClient()
    client = MongoClient(connection_string)
    db = client["stackoverflow"]
    if verbose:
      print("DB loaded with success, list of collections:\n",db.list_collection_names())
    return db
  except Exception as err:
    print(err)

def get_query(terms,verbose=False,limit=1):
  """ straightforward query to mongodb, returns a list of items(qs)"""
  res = db.questions.find(
    { "$text": { "$search": terms } },
    { "score": { "$meta": "textScore" } }
  ).limit(limit)

  res.sort([("score", { "$meta": "textScore" })])

  res = [r for r in res]

  if verbose:
    for r in res:
        print(r["Id"]," -- ",r["Title"]," ==> ",r["score"])

  return res

def filter_qs(ls_qs,threshold=2.0):
  return [q for q in ls_qs if q['score']>=threshold]

def get_best_answer(id):
  children =  list(db.answers.find({"ParentId":id}))
  children =  sorted(children, key=lambda k: k['stackoverflow_score'],reverse=True)
  if len(children)>0:
    return children[0]
  else:
    return None

def return_thread_link(id):
  return f'https://stackoverflow.com/questions/{id}/'

def define_response(text):
  ls_qs = get_query(terms=text,verbose=False)
  ls_qs = filter_qs(ls_qs)
  if len(ls_qs)<1:
    return {"status":"Not OK" ,
            "Body":"I apologize. I do not know about your question."}
  else:
    id = ls_qs[0]['Id']
    besti = get_best_answer(id)
    if besti:
      link = return_thread_link(id)
      besti['link'] = link
      besti['status'] = "OK"
      return besti
    else:
      return {"status":"Not OK" ,
            "Body":"It seems there are no good answers for your question."}

nltk.data.path.append('./chatbot/nltk_data')

try:
  nltk.download('punkt', download_dir='./chatbot/nltk_data')
  nltk.download('wordnet', download_dir='./chatbot/nltk_data')
except:
  print("Internet connection issue")


app = Flask(__name__)
CORS(app)



load_dotenv(".env")
connection_string = os.environ.get("DB_CONNECTION")

db = connect_db(connection_string=connection_string ,verbose=False)

os.environ['CUDA_VISIBLE_DEVICES'] = "0"


limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "120 per hour"]
)


model = load_model('chatbot/chatbot_model.h5')
intents = json.loads(open('chatbot/intents.json').read())
words = pickle.load(open('chatbot/words.pkl','rb'))
classes = pickle.load(open('chatbot/classes.pkl','rb'))



def clean_up_sentence(sentence):
    # tokenize the pattern - split words into array
    sentence_words = nltk.word_tokenize(sentence)
    # stem each word - create short form for word
    sentence_words = [lemmatizer.lemmatize(word.lower()) for word in sentence_words]
    return sentence_words


def bow(sentence, words, show_details=True):
    # tokenize the pattern
    sentence_words = clean_up_sentence(sentence)
    # bag of words - matrix of N words, vocabulary matrix
    bag = [0]*len(words) 
    for s in sentence_words:
        for i,w in enumerate(words):
            if w == s: 
                # assign 1 if current word is in the vocabulary position
                bag[i] = 1
                if show_details:
                    print ("found in bag: %s" % w)
    return(np.array(bag))


def predict_class(sentence, model):
    # filter out predictions below a threshold
    p = bow(sentence, words,show_details=False)
    res = model.predict(np.array([p]))[0]
    ERROR_THRESHOLD = 0.25
    results = [[i,r] for i,r in enumerate(res) if r>ERROR_THRESHOLD]
    # sort by strength of probability
    results.sort(key=lambda x: x[1], reverse=True)
    return_list = []
    for r in results:
        return_list.append({"intent": classes[r[0]], "probability": str(r[1])})
    return return_list


def getQuestionAnswer(sentence):
    answer = define_response(sentence)
    return answer

def getResponse(sentence, ints, intents_json):
    tag = ints[0]['intent']
    if tag == 'question':
        result = getQuestionAnswer(sentence)
    else:
        list_of_intents = intents_json['intents']
        for i in list_of_intents:
            if(i['tag']== tag):
                result = random.choice(i['responses'])
                break
    return result

def parse_json(data):
    return json.loads(json_util.dumps(data))

@app.route('/', methods=['GET','POST'])
@limiter.limit("120 per hour")
def home():
    # data = request.json
    # text = data["text"]
    # ints = predict_class(text, model)
    # res = getResponse(text, ints, intents)
    # response = parse_json(res) #jsonify(res)
    # #response.headers.add('Access-Control-Allow-Origin', '*')
    return "<p> The app should be working </p>"

@app.route('/response', methods=['POST'])
@limiter.limit("120 per hour")
def chatbot_response():
    data = request.json
    text = data["text"]
    ints = predict_class(text, model)
    res = getResponse(text, ints, intents)
    response = parse_json(res) #jsonify(res)
    #response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == "__main__":
  app.run(debug=True)
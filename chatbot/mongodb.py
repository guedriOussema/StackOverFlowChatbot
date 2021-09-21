from pymongo import MongoClient
import pymongo
#there can be an error when you must do this: !pip install pymongo["srv"]

#must be in .env

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


if __name__ == "__main__":

  #test code here

  from dotenv import load_dotenv
  import os
  load_dotenv("../.env")
  load_dotenv(".env") #DEPEND ON THE WORKING DIRECTORY

  
  connection_string = os.environ.get("DB_CONNECTION")
  print("THIS IS CONNECTION STRING: ",connection_string)


  terms = "index out of range python"

  exact_query = f"\"{terms}\""

  db = connect_db(connection_string=connection_string ,verbose=False)
  res = define_response(text=terms)
  print(res)
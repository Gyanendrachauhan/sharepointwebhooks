from flask_cors import CORS
from dotenv import load_dotenv
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from flask import Flask, request,jsonify
from datetime import datetime
import pytz
from flask import Flask, request,jsonify
import json,os,requests
import logging

cwd = os.getcwd()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

conversation = None
app = Flask(__name__)


data_d = {}
chat_history_payload = {}

def get_pdf_texts(pdf_docs):
    print(pdf_docs)
    text = ""
    for pdf in pdf_docs:
        loader = PyPDFLoader(pdf)
        pages = loader.load_and_split()
        for page in pages:
            text += page.page_content
    return text


def get_text_chunks(raw_text):
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(raw_text)
    return chunks


def get_vectorstore(text_chunks):
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore


def get_conversation_chain(vectorstore):
    # Context size if 3800 by default
    # llm = ChatOpenAI()
    llm = ChatOpenAI(model_name='gpt-3.5-turbo-16k')
    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversation_chain


def handle_userinput(user_question):
    global conversation
    response = conversation({'question': user_question})

    # store updated conversation object to the dictionary data_d
    chat_history = response['chat_history']
    return chat_history


def upload(pdf_docs):
    # Check env load
    print("Env files Loaded")
    load_dotenv()


    # get pdf text
    raw_text = get_pdf_texts(pdf_docs)

    # Check if the upladed document could not be parsed

    if len(raw_text) == 0:
            return jsonify({"message": "Unreadable document","success":True}), 400

    # get the text chunks
    text_chunks = get_text_chunks(raw_text)

    # create vector store
    vectorstore = get_vectorstore(text_chunks)

    # Create conversation chain
    global conversation
    conversation = get_conversation_chain(vectorstore)

    # Store conversation chain corresponding to this user email
    # data_d[email] = conversation

    return 200




def message(question_payload):


        # Store question in  history
    # try:
    #     chat_history_payload[email]['messages'].append(question_payload)
    # except:
    #     chat_history_payload[email].update({'messages': []})
    #     chat_history_payload[email]['messages'].append(question_payload)

        load_dotenv()

        # Get the question string from the input string
        question = question_payload
        # input question
        print(question)


        chat_history = handle_userinput(question)
        # print(chat_history)

        message_lis = [message.content for message in chat_history]


        response  = message_lis[-1]
        return response


load_dotenv()
# Replace these variables with your actual values
client_id = os.getenv('client_id')
client_secret = os.getenv('client_secret')
tenant_id = os.getenv('tenant_id')
resource = os.getenv('resource')
site_id = os.getenv('site_id')

base_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items'

def get_access_token():
    url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    body = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': resource + '/.default'
    }

    try:
        response = requests.post(url, headers=headers, data=body)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.HTTPError as err:
        logger.error(f"Error obtaining access token: {err}")
        return None




def download_pdf_files(folder_id, folder_name, access_token, base_url):
    all_files = []
    url = f'{base_url}/{folder_id}/children'
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.HTTPError as err:
        logger.error(f"Failed to list items in folder {folder_name}. Error: {err}")
        return [], []

    for item in response.json().get('value', []):
        all_files.append(os.path.join(folder_name, item['name']))

        if 'folder' in item:
            _, child_files = download_pdf_files(item['id'], os.path.join(folder_name, item['name']), access_token, base_url)
            all_files.extend(child_files)
        elif 'file' in item and item['name'].endswith('.pdf'):
            local_file_path = os.path.join('local_directory', folder_name, item['name'])

            if not os.path.exists(local_file_path):
                file_url = f'{base_url}/{item["id"]}/content'
                try:
                    file_response = requests.get(file_url, headers=headers, stream=True)
                    file_response.raise_for_status()
                except requests.HTTPError as err:
                    logger.error(f"Failed to download file {item['name']}. Error: {err}")
                    continue

                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                with open(local_file_path, 'wb') as local_file:
                    for chunk in file_response.iter_content(chunk_size=1024):
                        if chunk:
                            local_file.write(chunk)

    return "Download successful!", all_files


def clean_local_directory(all_files):
    root_directory_path = r'C:\Users\Gyani\PycharmProjects\sharepointfinal\local_directory'
    for foldername, _, filenames in os.walk(root_directory_path):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(foldername, filename), root_directory_path)
            if rel_path not in all_files:
                os.remove(os.path.join(foldername, filename))



def upload_pdfs_to_server(filename_req):
    logger.info(f"Expected filenames: {filename_req}")
    access_token = get_access_token()
    base_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items'

    if not access_token:
        logger.error("Failed to retrieve access token.")
        return jsonify({"error": "Failed to retrieve access token"}), 401

    result, all_files = download_pdf_files('root', '', access_token, base_url)
    logger.info(f"All files downloaded: {all_files}")

    root_directory_path = r'C:\Users\Gyani\PycharmProjects\sharepointfinal\local_directory'
    files_list = []

    for foldername, _, filenames in os.walk(root_directory_path):
        for filename in filenames:
            if filename.endswith('.pdf') and filename in filename_req:
                file_path = os.path.join(foldername, filename)
                files_list.append(file_path)

    logger.info(f"Files to upload: {files_list}")
    upload_response = upload(files_list)

    if upload_response != 200:
        logger.error(f"Upload failed with response: {upload_response}")
        return jsonify({"error": "Failed to upload PDFs", "response": upload_response.text}), upload_response.status_code

    logger.info("Upload successful!")
    return 200

@app.route("/webhook", methods=['POST'])
def webhook():
    access_token = get_access_token()
    if not access_token:
        print("Failed to retrieve access token.")
        exit()
    base_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items'
    folder_id = "root"
    folder_name = ""
    result, all_files = download_pdf_files(folder_id, folder_name, access_token,base_url)
    clean_local_directory(all_files)
    print(result)

    payload = request.form
    data = payload['intent']
    data1 = json.loads(data)
    action = data1['fulfillment']['action']
    parameters = data1['fulfillment']['parameters']

    if action =="action-category-question":
        question = parameters['question']
        print(question)
        x = message(question)
        print(x)
        c = {"message": x, "id": 40, "userInput": True, "trigger": 400}
        return jsonify(c)

    elif action == "action-category-faq-ma":
        # Present the list of filenames
        root_directory_path = r'C:\Users\Gyani\PycharmProjects\sharepointfinal\local_directory'
        filenames = [filename for foldername, _, filenames in os.walk(root_directory_path)
                     for filename in filenames if filename.endswith('.pdf')]

        selected_list = [{"value": filename, "label": filename} for filename in filenames]

        return jsonify({
        "id": 302,
        "message": "Welcome to our Sharepoint Site and select files for Q&A",
        "metadata": {
            "message": "something went wrong. Submit details again",
            "payload": [
                {
                    "data": {
                        "name": "Checkbox",
                        "title": "Checkbox",
                        "options": selected_list
                    },
                    "name": "Checkbox",
                    "type": "checkbox",
                    "validation": "required"
                },
                {
                    "type": "submit",
                    "label": "Submit",
                    "message": "Response Submitted",
                    "trigger": 3020,
                    "formAction": "/",
                    "requestType": "POST"
                },
                {
                    "type": "cancel",
                    "label": "Cancel",
                    "message": "Cancelled",
                    "trigger": 30
                }
            ],
            "templateId": 13,
            "contentType": "300"
        },
        "userInput": False,
        "fulfillment": {
            "action": "action-category-faq-ma",
            "parameters": {
                "faq": "{previousValue:30}"
            },
            "previousIntent": 30
        }
    })

    elif action == "action-category-faq-ma-ans":
        selected_filename = [i.replace('{previousValue:', '').replace('}', '') for i in parameters['faqans']['Checkbox']]

        # Trigger the upload for the selected file
        # response = requests.get(f"http://127.0.0.1:5000/download-and-upload-pdfs?filename={selected_filename}")
        response=upload_pdfs_to_server(selected_filename)

        response_selected_filename = ",".join(i for i in selected_filename)
        print(response_selected_filename)

        if response == 200:
            return jsonify({
                "id": 3020,
                "message": f"<b>{str(response_selected_filename)}</b> uploaded successfully",
                "metadata": {
                    "payload": [{
                        "image": "https://img.icons8.com/flat-round/2x/circled-left.png",
                        "label": "Ask Question",
                        "value": "Ask Question",
                        "trigger": 4
                    }],
                    "templateId": 6
                },
                "fulfillment": {
                    "action": "action-category-faq-ma-ans",
                    "parameters": {},
                    "previousIntent": 302
                },
                "userInput": False
            })
        else:
            return jsonify({
                "error": f"Failed to upload {selected_filename}",
                "response": response,
                "id": 304,  # You can set the appropriate ID
                "userInput": True,
                "trigger": 304  # You can set the appropriate trigger
            })
    return jsonify({"error": "Unknown action"})

if __name__=="__main__":
    app.run(debug=True,port=5000)








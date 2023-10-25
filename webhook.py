from flask import Flask,jsonify,json,request
from dotenv import load_dotenv
import os
from llm import message
from share import get_access_token,download_pdf_files,clean_local_directory,upload_pdfs_to_server
cwd = os.getcwd()
app = Flask(__name__)

client_id = os.getenv('client_id')
client_secret = os.getenv('client_secret')
tenant_id = os.getenv('tenant_id')
resource = os.getenv('resource')
site_id = os.getenv('site_id')
base_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items'
load_dotenv()
auth_li={}

@app.route("/webhook", methods=['POST'])
def webhook():
    access_token = get_access_token()
    if not access_token:
        print("Failed to retrieve access token.")
        exit()
    base_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items'
    folder_id = "root"
    folder_name = ""
    result, all_files,file_url_dict  = download_pdf_files(folder_id, folder_name, access_token,base_url)
    clean_local_directory(all_files)
    print(all_files)
    print(file_url_dict)
    print(result)

    payload = request.form
    data = payload['intent']
    data1 = json.loads(data)
    action = data1['fulfillment']['action']
    parameters = data1['fulfillment']['parameters']
    if action == "action-vecv-user-pre-login":
            chatId = data1["chatId"]
            auth_li[chatId] = {}
            res_json = {"id":3,"message":"Get verified from AD","fulfillment":{"action":"action-vecv-user-pre-login","parameters":{"details":"{previousValue:2}"},"previousIntent":2},"metadata":{"payload":[{"url":f"http://localhost:6040/login?cid={chatId}","name":". Go to AD Login page","image":"https://i.ibb.co/KNFsKWX/images.png","type":"link","value":"Go to AD Login page","trigger":210,"openLinkInNewTab":True}],"templateId":6},"userInput":False}

            return res_json
    elif action == "action-user-vecv-login":
            chatId = data1["chatId"]
            print(chatId)
            with open(r"D:\python projects\PycharmProjects\sharepointfinal\auth.txt","r") as f:
                txt=f.read()
            if len(txt)!=0:
                l =  txt.split(":")
                c_i = l[0]
                auth = l[1]
                print(c_i)
                print(auth)
                if chatId == c_i:
                    if auth == "true":
                        return data1


            res_json = {"id": 210, "message": "Not verified! <b>Try Again", "metadata": {
                    "payload": [{"label": "Validate", "value": "Validate ", "trigger": 2100},
                                {"image": "https://img.icons8.com/flat-round/2x/circled-left.png", "label": "Go Back",
                                 "value": "Go Back", "trigger": 3}], "templateId": 6}, "userInput": False}
            return res_json





    if action =="action-category-question":
        question = parameters['question']
        print(question)
        x = message(question)
        print(x)
        c = {"message": x, "id": 40, "userInput": True, "trigger": 400}
        return jsonify(c)

    elif action == "action-category-faq-ma":
        # Present the list of filenames from SharePoint
        filenames = [os.path.basename(file) for file in all_files if file.endswith('.pdf')]
        selected_list = [{"value": filename, "label": filename} for filename in filenames]
        print(file_url_dict)
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
        response = upload_pdfs_to_server(selected_filename)
        response_selected_filename = "".join("<li>"+i+"</li>" for i in selected_filename)

        if response == 200:
            return jsonify({
                "id": 3020,
                "message":"<ul>"+response_selected_filename + "</ul>Uploaded successfully",
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
        "response_text": response.text if hasattr(response, 'text') else str(response),
        "response_status": response.status_code if hasattr(response, 'status_code') else None,
        "id": 304,  # You can set the appropriate ID
        "userInput": True,
        "trigger": 304  # You can set the appropriate trigger # You can set the appropriate trigger
            })
    return jsonify({"error": "Unknown action"})

if __name__=="__main__":
    app.run(debug=True,port=5000)

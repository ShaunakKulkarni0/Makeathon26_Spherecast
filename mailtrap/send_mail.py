import base64
import time
import boto3
import mailtrap as mt

# 1. Convert your PDF into a Base64 string
with open("/Users/dibbo/Downloads/Technical Data Sheet (TDS).pdf", "rb") as pdf_file:
    binary_data = pdf_file.read()
    base64_string = base64.b64encode(binary_data).decode('utf-8')

# 2. Create the Attachment object
attachment = mt.Attachment(
    content=base64_string,
    filename="Technical_Sheet_purebulk.pdf",
    disposition=mt.Disposition.ATTACHMENT,
    mimetype="application/pdf"
)

# 3. Add it to the email
mail = mt.Mail(
    sender=mt.Address(email="test@example.com", name="Sender"),
    to=[mt.Address(email="claudeopus4.7@spherecast.ai")],
    subject="Attachment Prototype",
    text="Here is your PDF!",
    attachments=[attachment]
)

# 4. Send email to Mailtrap
print("Sending email to Mailtrap...")
client = mt.MailtrapClient(token="266e12dab50ef1c62de3afffdfb7c333", sandbox=True, inbox_id=4557417)
client.send(mail)
print("Success!")

# --- NEW AWS TRIGGER LOGIC ---

# Delay for 5 seconds to let Mailtrap process the email
print("Waiting 5 seconds...")
time.sleep(5)

# Trigger the AWS Lambda function directly
print("Invoking AWS Lambda...")

# Initialize the AWS Lambda client (Make sure the region matches where your Lambda lives)
lambda_client = boto3.client('lambda', region_name='eu-west-1') 

# Replace 'FetchMailtrapLambda' with the EXACT name of your Lambda function in AWS
response = lambda_client.invoke(
    FunctionName='getMail', 
    InvocationType='RequestResponse' # This tells boto3 to wait and return the Lambda's result
)

# Read and print what the Lambda function returned
response_payload = response['Payload'].read().decode('utf-8')
print(f"AWS Lambda Response: {response_payload}")
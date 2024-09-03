import argparse
import datetime
import json
import requests
import form
import random
import openai

def fill_with_json_values(type_id, entry_id, options, required=False, entry_name='', json_values=None):
    ''' Fill form entry with provided JSON values '''
    full_entry_id = "entry." + str(entry_id)
    if json_values and full_entry_id in json_values:
        return json_values[full_entry_id]
    
    # Fallback to random value if JSON does not have a specific value
    if type_id in [0, 1]:  # Short answer and Paragraph
        return '' if not required else 'Ok!'
    if type_id in [2, 3, 5, 7]:  # Multiple choice, Dropdown, Linear scale, Grid choice
        return random.choice(options)
    if type_id == 4:  # Checkboxes
        return random.sample(options, k=random.randint(1, len(options)))
    if type_id == 9:  # Date
        return datetime.date.today().strftime('%Y-%m-%d')
    if type_id == 10:  # Time
        return datetime.datetime.now().strftime('%H:%M')
    
    return ''

def generate_request_body(url: str, only_required=False, json_values=None):
    ''' Generate request body data using JSON values '''
    data = form.get_form_submit_request(
        url,
        only_required=only_required,
        fill_algorithm=lambda type_id, entry_id, options, required, entry_name: fill_with_json_values(
            type_id, entry_id, options, required, entry_name, json_values
        ),
        output="return",
        with_comment=False
    )
    print(f"Data: {data}")
    data = json.loads(data)
    return data

def submit(url: str, data: any):
    ''' Submit form to url with data '''
    url = form.get_form_response_url(url)
    print(f"Data: {data}", flush=True)
   
    res = requests.post(url, data=data, timeout=5)
    if res.status_code != 200:
        print(f"Error! Can't submit form, status code: {res.status_code}")
    else:
        print("Form submitted successfully!")

# Set up your OpenAI API key
api_key = 'sk-proj'

# Initialize the OpenAI client
client = openai.OpenAI(
    api_key=api_key,  # Ensure your API key is set in the environment
)

def generate_prompt(format_of_generated_data, num_responses=5):
    """Generate the prompt for GPT-4 based on the format_of_generated_data."""
    return (
        f"Please generate {num_responses} realistic answers for the following Google Form in the JSON format:\n"
        f"{format_of_generated_data}\n"
        f"For fields with predefined options, choose an appropriate option. If the option 'ANY TEXT!!' is present, "
        f"either choose an available option or generate a custom text response. Never leave 'ANY TEXT!!' as the answer.\n"
        f"Ensure that email is realistic and follows the correct format. You can generate random names, emails, "
        f"Names not always have to be with second names, and emails can be random but should look realistic.\n"
        f"Return the answers as a JSON array with {num_responses} elements, without any comments."
    )

def call_gpt4(prompt):
    """Call GPT-4 model to generate form responses using the new OpenAI client."""
    chat_completion = client.chat.completions.create(
        model="gpt-4o",  # Specify the model, change to "gpt-4-turbo" if needed
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1500,
        temperature=0.7
    )
    
    # Extract the JSON array of responses from GPT-4's output
    responses = []
    try:
        # Get the content from the response
        content = chat_completion.choices[0].message.content.strip()

        # Check if the content is wrapped in triple backticks and remove them
        if content.startswith("```json") and content.endswith("```"):
            content = content[7:-3].strip()  # Remove the ```json and ``` markers

        print(f"Response from GPT-4:\n{content}")
        # Parse the JSON data
        response_data = json.loads(content)

        if isinstance(response_data, list):  # Ensure the response is a list
            responses = response_data
        else:
            print("Error: The generated output is not a JSON array.")
    except json.JSONDecodeError:
        print("Error decoding JSON response from GPT-4.")
    
    return responses

def fill_with_llm(url: str, total_responses=70, batch_size=3):
    """Fill form with LLM-generated values and prepare for submission."""
    # Step 1: Generate the prompt based on the form structure
    format_of_generated_data = form.get_form_submit_request(url, only_required=False, output="return", with_comment=True)
    
    prompt = generate_prompt(format_of_generated_data, num_responses=batch_size)
    print(f"Generated prompt:\n{prompt}")
    all_responses = []

    # Step 2: Generate responses in batches
    while len(all_responses) < total_responses:
        batch_responses = call_gpt4(prompt)
        all_responses.extend(batch_responses)
        if len(all_responses) >= total_responses:
            all_responses = all_responses[:total_responses]  # Trim if we have too many
    
    # Step 3: Combine all responses into a single JSON array
    combined_responses = json.dumps(all_responses, indent=4)
    print(f"Generated responses:\n{combined_responses}")

    # Step 4: Ask the user if they want to submit the generated data
    confirmation = input("Do you want to submit these responses? (yes/no): ").strip().lower()
    if confirmation == 'yes':
        # Submit the generated data using the existing main function's logic
        main(url, json_file=None, only_required=False, json_data=all_responses)
    else:
        print("Submission aborted by the user.")

def main(url, json_file=None, only_required=False, json_data=None):
    try:
        if json_file:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        
        # Ensure json_data is a list of objects
        if not isinstance(json_data, list):
            print("Error! JSON data must be a list of form entry objects.")
            return

        for index, json_values in enumerate(json_data):
            print(f"\nSubmitting form {index + 1}/{len(json_data)}")
            payload = generate_request_body(url, only_required=only_required, json_values=json_values)
            print(f"Form data {payload}")
            submit(url, payload)
            print("Done with this form!")
    
    except Exception as e:
        print("Error!", e)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Submit Google Form with custom data from a JSON file')
    parser.add_argument('url', help='Google Form URL')
    parser.add_argument('json_file', help='Path to JSON file containing form data')
    parser.add_argument('-r', '--required', action='store_true', help='Only include required fields')
    args = parser.parse_args()
    # main(args.url, args.json_file, args.required)
    fill_with_llm(args.url, total_responses=40)



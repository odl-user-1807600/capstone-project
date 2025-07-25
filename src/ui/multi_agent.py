import asyncio
import re
import os
import subprocess
from typing import List

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.kernel import Kernel

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# --- UPDATED TERMINATION STRATEGY ---
class ApprovalTerminationStrategy(TerminationStrategy):
    """
    Terminates the conversation when the last message content is 'READY FOR USER APPROVAL'.
    This is expected to come from the ProductOwner agent.
    """
    async def should_terminate(self, agent, history: ChatHistory) -> bool:
        """Check if the agent group should terminate."""
        if not history:
            return False

        # Get the last message in the chat history
        last_message = history[-1]

        # Check if the last message content is "READY FOR USER APPROVAL"
        if last_message.content and last_message.content.strip().upper() == "READY FOR USER APPROVAL":
            print("\n--- 'READY FOR USER APPROVAL' received. Pausing for user input. ---")
            return True
        
        return False

# --- UNCHANGED POST-PROCESSING FUNCTION ---
def extract_and_save_html(history: ChatHistory, filename: str = "index.html"):
    """
    Extracts HTML, saves it, and then calls a script to push it to GitHub.
    """
    print("\n\n----- POST-PROCESSING STEP -----")
    
    # Filter for messages from the SoftwareEngineer agent by name
    engineer_messages = [
        msg.content for msg in history.messages if msg.name == "SoftwareEngineer"
    ]

    if not engineer_messages:
        print("No messages from SoftwareEngineer found. No file created.")
        return

    html_snippets = []
    for message in engineer_messages:
        # Regex to find ```html ... ``` blocks
        found = re.findall(r"```html\n(.*?)\n```", message, re.DOTALL)
        if found:
            html_snippets.extend(found)

    if not html_snippets:
        print("SoftwareEngineer did not provide any HTML code in the correct format. No file created.")
        return
        
    final_html = "\n".join(html_snippets)

    try:
        with open(filename, "w") as f:
            f.write(final_html)
        print(f"✅ Successfully extracted HTML and saved to '{filename}'")
    except IOError as e:
        print(f"❌ Error saving file: {e}")
        return

    # --- Call the bash script to push to GitHub ---
    try:
        print("\n----- INITIATING GIT PUSH -----")
        commit_message = f"feat: AI-generated update for {filename}"
        script_path = "./push_to_github.sh"
        
        if not os.path.exists(script_path):
             print(f"❌ Error: The script '{script_path}' was not found.")
             return

        subprocess.run(["chmod", "+x", script_path], check=True)
        
        result = subprocess.run(
            ["/bin/bash", script_path, commit_message], 
            check=True, 
            capture_output=True, 
            text=True
        )
        print(result.stdout)
        print("✅ Git push process completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during Git push process:")
        print(e.stderr)

# --- REVISED MAIN EXECUTION LOGIC ---
async def run_multi_agent(user_prompt: str):
    """Implements and runs the multi-agent system with a human approval step."""
    kernel = Kernel()
    # Ensure you have AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME in your .env
    kernel.add_service(AzureChatCompletion())

    # --- AGENTS WITH USER-PROVIDED PROMPTS ---
    business_analyst_agent= ChatCompletionAgent(
        kernel=kernel, 
        name="BusinessAnalyst", 
        instructions="You are a Business Analyst which will take the requirements from the user (also known as a 'customer') and create a project plan for creating the requested app. The Business Analyst understands the user requirements and creates detailed documents with requirements and costing. The documents should be usable by the SoftwareEngineer as a reference for implementing the required features, and by the Product Owner for reference to determine if the application delivered by the Software Engineer meets all of the user's requirements.",
    )
    software_engineer_agent= ChatCompletionAgent(
        kernel=kernel,
        name="SoftwareEngineer", 
        instructions="You are a Software Engineer, and your goal is create a web app using HTML and JavaScript by taking into consideration all the requirements given by the Business Analyst. The application should implement all the requested features. Deliver the code to the Product Owner for review when completed. You can also ask questions of the BusinessAnalyst to clarify any requirements that are unclear.",
    )
    product_owner_agent= ChatCompletionAgent(
        kernel=kernel, 
        name="ProductOwner", 
        instructions="You are the Product Owner which will review the software engineer's code to ensure all user  requirements are completed. You are the guardian of quality, ensuring the final product meets all specifications. IMPORTANT: Verify that the Software Engineer has shared the HTML code using the format ```html [code] ```. This format is required for the code to be saved and pushed to GitHub. Once all client requirements are completed and the code is properly formatted, reply with 'READY FOR USER APPROVAL'. If there are missing features or formatting issues, you will need to send a request back to the SoftwareEngineer or BusinessAnalyst with details of the defect.",
    )

    # Create the group chat with the termination strategy
    group_chat = AgentGroupChat(
        agents=[business_analyst_agent, software_engineer_agent, product_owner_agent],
        termination_strategy=ApprovalTerminationStrategy()
    )

    # --- FIX: Add the initial message directly to the group's internal history ---
    initial_message = ChatMessageContent(role="user", content=user_prompt, name="User")
    group_chat.history.add_message(message=initial_message)

    print(f"=============================\nStarting Agent Collaboration for: '{user_prompt}'\n=============================\n")
    # print(f"[{initial_message.name}]: {initial_message.content}\n") # Manually print the first message

    # --- INVOCATION LOOP ---
    # The final_history will be a copy of the group's history at the end.
    # We invoke with no arguments, letting the chat run on its internal state.
    async for message in group_chat.invoke():
        print(f"[{message.name}]]: {message.content}\n")

    # After the loop, the group_chat.history contains the full conversation
    final_history = group_chat.history

    print("\n=============================\nAgent Collaboration Finished\n=============================")
    
    # --- HUMAN-IN-THE-LOOP APPROVAL STEP ---
    if final_history.messages and final_history.messages[-1].content.strip().upper() == "READY FOR USER APPROVAL":
        print("\n✅ The agents have completed their work. Please review the conversation.")
        
        while True:
            user_input = input(">>> Type 'APPROVED' to finalize and push, or 'REJECT' to cancel: ")
            if user_input.strip().upper() == "APPROVED":
                print("\nUser has approved. Proceeding with post-processing...")
                extract_and_save_html(final_history)
                break 
            elif user_input.strip().upper() == "REJECT":
                print("\nUser has rejected the work. Exiting without action.")
                break
            else:
                print("   Invalid input. Please try again.")
    else:
        print("\nChat concluded without reaching the user approval stage. Exiting.")


if __name__ == "__main__":
    initial_request = (
        "Create a simple landing page for a new SaaS product called 'AI-Boost'. "
        "It needs a title, a brief description, and a call-to-action button that says 'Sign Up Now'."
        "All code should be in a single `index.html` file."
    )
    asyncio.run(run_multi_agent(initial_request))

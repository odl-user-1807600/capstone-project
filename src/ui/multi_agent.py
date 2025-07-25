import asyncio
import re
import os
import subprocess # <-- Import the subprocess module


from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.agents.strategies.selection.kernel_function_selection_strategy import (
    KernelFunctionSelectionStrategy,
)
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel



class ApprovalTerminationStrategy(TerminationStrategy):
    """A strategy for determining when an agent should terminate."""
 
    async def should_agent_terminate(self, agent, history):
        """Check if the agent should terminate."""
        if not chat_history or not chat_history.messages:
            return False

        # Get the last message in the chat history
        last_message = chat_history.messages[-1]

        # Check if the last message is from a user and its content is "APPROVED"
        if last_message.author_role == AuthorRole.USER and \
           last_message.content and \
           last_message.content.strip().upper() == "APPROVED":
            print("\n--- User typed 'APPROVED'. Terminating chat. ---")
            return True
        return False

def extract_and_save_html(history: ChatHistory, filename: str = "index.html"):
    """
    Extracts HTML, saves it, and then calls a script to push it to GitHub.
    """
    print("\n\n----- POST-PROCESSING STEP -----")
    
    engineer_messages = [
        msg.content for msg in history.messages if msg.author_name == "SoftwareEngineer"
    ]

    if not engineer_messages:
        print("No messages from SoftwareEngineer found. No file created.")
        return

    html_snippets = []
    for message in engineer_messages:
        found = re.findall(r"```html\n(.*?)\n```", message, re.DOTALL)
        if found:
            html_snippets.extend(found)

    if not html_snippets:
        print("SoftwareEngineer did not provide any HTML code. No file created.")
        return
        
    final_html = "\n".join(html_snippets)

    try:
        with open(filename, "w") as f:
            f.write(final_html)
        print(f"✅ Successfully extracted HTML and saved to '{filename}'")
    except IOError as e:
        print(f"❌ Error saving file: {e}")
        return # Exit if file saving fails

    # --- NEW: Call the bash script to push to GitHub ---
    try:
        print("\n----- INITIATING GIT PUSH -----")
        # Define a commit message
        commit_message = f"feat: AI-generated update for {filename}"
        
        # Ensure the script is executable before running
        script_path = "./push_to_github.sh"
        subprocess.run(["chmod", "+x", script_path], check=True)
        
        # Run the script. It will handle the add, commit, and push.
        # The 'check=True' will raise an exception if the script returns a non-zero exit code.
        result = subprocess.run(
            ["/bin/bash", script_path, commit_message], 
            check=True, 
            capture_output=True, 
            text=True
        )
        print(result.stdout) # Print the output from the bash script
        print("✅ Git push process completed successfully.")

    except FileNotFoundError:
        print(f"❌ Error: The script '{script_path}' was not found.")
    except subprocess.CalledProcessError as e:
        # This will catch errors from the git commands within the script
        print(f"❌ Error during Git push process:")
        print(e.stderr) # Print the error output from the script

async def run_multi_agent(input: str):
    """implement the multi-agent system."""
    # Define the kernel
    kernel = Kernel()

    # Add the chat completion service to the kernel
    kernel.add_service(AzureChatCompletion())

    # Create the agents using the kernel
    businessAnalystAgent = ChatCompletionAgent(
        kernel=kernel, 
        name="BusinessAnalyst", 
        instructions="You are a Business Analyst which will take the requirements from the user (also known as a 'customer') and create a project plan for creating the requested app. The Business Analyst understands the user requirements and creates detailed documents with requirements and costing. The documents should be usable by the SoftwareEngineer as a reference for implementing the required features, and by the Product Owner for reference to determine if the application delivered by the Software Engineer meets all of the user's requirements.",
    )
    sofwareEngineerAgent = ChatCompletionAgent(
        kernel=kernel,
        name="SoftwareEngineer", 
        instructions="You are a Software Engineer, and your goal is create a web app using HTML and JavaScript by taking into consideration all the requirements given by the Business Analyst. The application should implement all the requested features. Deliver the code to the Product Owner for review when completed. You can also ask questions of the BusinessAnalyst to clarify any requirements that are unclear.",
    )
    productOwnerAgent = ChatCompletionAgent(
        kernel=kernel, 
        name="ProductOwner", 
        instructions="You are the Product Owner which will review the software engineer's code to ensure all user  requirements are completed. You are the guardian of quality, ensuring the final product meets all specifications. IMPORTANT: Verify that the Software Engineer has shared the HTML code using the format ```html [code] ```. This format is required for the code to be saved and pushed to GitHub. Once all client requirements are completed and the code is properly formatted, reply with 'READY FOR USER APPROVAL'. If there are missing features or formatting issues, you will need to send a request back to the SoftwareEngineer or BusinessAnalyst with details of the defect.",
    )

    approvalTerminationStrategy = ApprovalTerminationStrategy()
    groupChat = AgetGroupChat(
        agents= [businessAnalystAgent, softwareEngineerAgent, productOwnerAgent],
        termination_strategy= approvalTerminationStrategy
    )

    # Invoke the chat and let the agents collaborate
    responses = await chat.invoke(input=ChatHistory(messages=[(await retrieve_tool_call_results(message=initial_prompt, tool_call_results=[initial_prompt]))[0]]))
    
    return responses


    # 5. Execute the post-processing callback function: extract_and_save_html(chat_history)

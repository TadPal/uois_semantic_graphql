import xml.etree.ElementTree as ET
from typing import List, Dict, Any


def extract_prompts_from_chat_xml(xml_content: str) -> Dict[str, List[str]]:
    """
    Extract system prompts, user prompts, and assistant prompts (non-function calls) from XML chat history.

    Args:
        xml_content (str): The XML content as a string

    Returns:
        Dict[str, List[str]]: Dictionary containing lists of prompts categorized by role
    """
    try:
        # Parse the XML
        root = ET.fromstring(xml_content)

        # Initialize result dictionary
        result = {
            "system_prompts": [],
            "user_prompts": [],
            "assistant_prompts": [],
            "tool_prompts": [],
        }

        # Find all message elements
        messages = root.findall(".//message")

        for message in messages:
            role = message.get("role")

            # Check if message has function calls (finish_reason="tool_calls" or contains function_call)
            finish_reason = message.get("finish_reason")
            has_function_call = message.find("function_call") is not None

            if finish_reason == "tool_calls" or has_function_call:
                continue

            # Extract text content
            text_element = message.find("text")
            if text_element is not None and text_element.text:
                text_content = text_element.text.strip()

            function_result = message.find("function_result")
            if function_result is not None and function_result.text:
                text_content = function_result.text.strip()

                # Categorize by role
                if role == "system":
                    result["system_prompts"].append(text_content)
                elif role == "user":
                    result["user_prompts"].append(text_content)
                elif role == "assistant":
                    result["assistant_prompts"].append(text_content)
                elif role == "tool":
                    result["tool_prompts"].append(text_content)

        return result

    except ET.ParseError as e:
        raise ValueError(f"Invalid XML format: {e}")
    except Exception as e:
        raise RuntimeError(f"Error processing XML: {e}")


def print_extracted_prompts(prompts: Dict[str, List[str]]) -> None:
    """
    Pretty print the extracted prompts.

    Args:
        prompts (Dict[str, List[str]]): Dictionary containing categorized prompts
    """
    for category, prompt_list in prompts.items():
        print(f"\n{'='*50}")
        print(f"{category.upper().replace('_', ' ')}")
        print(f"{'='*50}")

        if not prompt_list:
            print("No prompts found in this category.")
        else:
            for i, prompt in enumerate(prompt_list, 1):
                print(f"\n[{i}] {prompt}")
                print("-" * 30)

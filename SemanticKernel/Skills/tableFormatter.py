import json
from typing import Annotated
from semantic_kernel.functions import kernel_function
from semantic_kernel.functions import KernelArguments

class TableFormatterPlugin:
    @kernel_function(
        name="formatAsTable",
        description="Formats a list of dictionaries (JSON string) into a Markdown table. Use this tool when the user specificly asks for data in a table format. Do not user if user do not ask for a table."
    )
    async def format_as_table(
        self,
        json_data: Annotated[str, "A JSON string representing a list of objects (dictionaries)."],
        arguments: KernelArguments = None
    ) -> str:
        """
        Converts JSON data to a formatted Markdown table.
        """
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            return "Invalid JSON data provided."

        if not isinstance(data, list) or not data:
            return "Data is not a list or is empty."

        headers = set()
        for item in data:
            if isinstance(item, dict):
                headers.update(item.keys())
        
        headers = sorted(list(headers))
        if not headers:
            return "No data found to create a table."

        markdown_table = "| " + " | ".join(headers) + " |\n"
        markdown_table += "|---" * len(headers) + "|\n"

        for item in data:
            if isinstance(item, dict):
                row_values = []
                for header in headers:
                    value = item.get(header, "")
                    row_values.append(str(value))
                markdown_table += "| " + " | ".join(row_values) + " |\n"
        
        return markdown_table